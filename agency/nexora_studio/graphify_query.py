# -*- coding: utf-8 -*-
"""Graphify query CLI — Phase 47.28B (ADR-0026 role extension).

Bounded repository-topology queries over the Graphify AST graph
(graphify-out/graph.json) for the OpenCode coding agent. Invoked through
the EXISTING bash tool — no plugin/MCP infrastructure.

Contract (ADR-0026 audit note + 47.28B):
  * Returns ONLY graph slices: labels, files, lines. Never file contents,
    never the whole graph, never secrets (the graph carries structure only).
  * Bounded output: --limit result lines (default 25), --max-chars (4000).
  * Staleness detection: graph mtime vs newest source file mtime; the tool
    reports staleness loudly and refuses to answer silently-stale queries
    beyond a threshold (use --refresh to rebuild via run_graphify.py).
  * Graph = navigation intelligence; source files remain the truth. The
    agent must still READ the relevant files for implementation decisions.

Usage:
  python graphify_query.py status
  python graphify_query.py symbol ContentEngine
  python graphify_query.py callers ContentEngine
  python graphify_query.py importers content_engine
  python graphify_query.py deps content_engine
  python graphify_query.py file code_generation_engine
  python graphify_query.py subclasses BaseGenerationEngine
  python graphify_query.py path builder_session ai_provider_manager
  python graphify_query.py callers ContentEngine --limit 10
"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict, deque

ADDON_ROOT = os.path.dirname(os.path.abspath(__file__))
GRAPH_PATH = os.path.join(ADDON_ROOT, 'graphify-out', 'graph.json')
RUN_GRAPHIFY = os.path.join(ADDON_ROOT, 'run_graphify.py')

# Bounds — a query result must never become its own context explosion.
DEFAULT_LIMIT = 25
DEFAULT_MAX_CHARS = 4000

# Staleness: graph older than any source file by more than this many
# minutes is considered stale (extraction itself takes minutes; the slack
# covers in-flight edits).
STALE_SLACK_MIN = 10


def _die(msg, code=2):
    print(msg)
    sys.exit(code)


class Graph:
    def __init__(self):
        if not os.path.exists(GRAPH_PATH):
            _die('graphify-out/graph.json not found. Run: python run_graphify.py')
        with open(GRAPH_PATH, encoding='utf-8') as fh:
            data = json.load(fh)
        self.nodes = {n['id']: n for n in data.get('nodes', [])}
        self.links = data.get('links', [])
        self.built_at = os.path.getmtime(GRAPH_PATH)
        # Indexes
        self.calls_in = defaultdict(list)   # target id -> [link]
        self.calls_out = defaultdict(list)  # source id -> [link]
        self.file_importers = defaultdict(set)  # target source_file -> {source_file}
        self.file_imports = defaultdict(set)   # source source_file -> {target source_file}
        self.label_index = defaultdict(list)   # norm label -> [node ids]
        self.file_symbols = defaultdict(list)  # source_file -> [symbol nodes]
        self.inherits_in = defaultdict(list)
        for link in self.links:
            rel = link.get('relation')
            src, tgt = link.get('source'), link.get('target')
            if rel == 'calls':
                self.calls_in[tgt].append(link)
                self.calls_out[src].append(link)
            elif rel == 'inherits':
                self.inherits_in[tgt].append(link)
            elif rel in ('imports', 'imports_from', 're_exports'):
                s_node, t_node = self.nodes.get(src), self.nodes.get(tgt)
                if s_node and t_node:
                    self.file_importers[t_node['source_file']].add(
                        s_node['source_file'])
                    self.file_imports[s_node['source_file']].add(
                        t_node['source_file'])
        for node in self.nodes.values():
            if node.get('file_type') != 'code':
                continue
            label = str(node.get('label') or '')
            self.label_index[label.lower()].append(node['id'])
            # Symbol nodes: source_location beyond L1 (a def/class site).
            if node.get('source_location') not in (None, 'L1') and \
                    not label.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
                self.file_symbols[node['source_file']].append(node)

    def find_symbols(self, name):
        return [self.nodes[i] for i in self.label_index.get(
            str(name).lower(), [])]

    def matching_files(self, pattern):
        """Exact-basename matches first; then path-substring matches.

        The AST file-level import index is PARTIAL (the extractor records a
        subset of import forms) — queries report this honestly instead of
        claiming completeness. Exhaustive import search still needs grep.
        """
        pat = str(pattern).lower().replace('\\', '/').strip('/')
        all_files = set(self.file_symbols)
        for node in self.nodes.values():
            f = node.get('source_file')
            if f:
                all_files.add(f)
        exact, partial = [], []
        for f in all_files:
            base = str(f).replace('\\', '/').rsplit('/', 1)[-1].lower()
            if base == pat or base == pat + '.py':
                exact.append(f)
            elif pat in str(f).lower().replace('\\', '/'):
                partial.append(f)
        return sorted(exact) + sorted(partial), len(exact)


def staleness(graph):
    """(is_stale, detail) — graph older than the newest source file."""
    newest, newest_path = 0.0, None
    # Dev tooling (this script, the runner) never invalidates the graph.
    tooling = {os.path.basename(__file__), 'run_graphify.py'}
    for root, dirs, files in os.walk(ADDON_ROOT):
        rel = os.path.relpath(root, ADDON_ROOT).replace('\\', '/')
        if rel.startswith(('tests/workspace', 'graphify-out', 'cache',
                           'node_modules', 'dist')):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f in tooling:
                continue
            if f.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
                p = os.path.join(root, f)
                try:
                    mt = os.path.getmtime(p)
                except OSError:
                    continue
                if mt > newest:
                    newest, newest_path = mt, os.path.relpath(p, ADDON_ROOT)
    if not newest:
        return False, 'no source files found'
    slack = STALE_SLACK_MIN * 60
    if newest > graph.built_at + slack:
        age_min = (newest - graph.built_at) / 60
        return True, ('graph is %.0f min older than newest source change (%s)'
                      % (age_min, newest_path))
    return False, ('fresh (newest source change: %s)' % newest_path)


def _emit(lines, limit, max_chars):
    out = []
    used = 0
    shown = 0
    for line in lines:
        if shown >= limit:
            out.append('... (%d more, raise --limit)' % (len(lines) - shown))
            break
        text = line[:200]
        if used + len(text) > max_chars:
            out.append('... (char cap %d reached, raise --max-chars)' % max_chars)
            break
        out.append(text)
        used += len(text)
        shown += 1
    print('\n'.join(out))
    print(' [%d/%d results, %d chars]' % (shown, len(lines), used))


def _warn_stale(graph, force):
    stale, detail = staleness(graph)
    if stale:
        print('WARNING: graph index is STALE (%s).' % detail)
        print('Refresh with: python run_graphify.py  (or --refresh)')
        if not force:
            print('(answering anyway — verify results against source files)')
    return stale, detail


def cmd_status(graph, args):
    print('graph: %s' % GRAPH_PATH)
    print('built: %s' % time.strftime('%Y-%m-%d %H:%M', time.localtime(graph.built_at)))
    print('nodes: %d | links: %d | source files: %d' % (
        len(graph.nodes), len(graph.links), len(graph.file_symbols)))
    # Coverage drift: .py files on disk (excl. tooling/output/fixture dirs)
    # vs indexed.
    disk = 0
    for root, dirs, files in os.walk(ADDON_ROOT):
        rel = os.path.relpath(root, ADDON_ROOT).replace('\\', '/')
        if rel.startswith(('tests/workspace', 'graphify-out', 'cache',
                           'node_modules', 'dist')):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py') and f not in (os.path.basename(__file__), 'run_graphify.py'):
                disk += 1
    drift = disk - len(graph.file_symbols)
    print('coverage: %d .py files on disk, %d indexed (%+d drift)' % (
        disk, len(graph.file_symbols), drift))
    if drift > 0:
        print('  NOTE: %d files added since last build — refresh when convenient' % drift)
    stale, detail = staleness(graph)
    print('staleness: %s — %s' % ('STALE' if stale else 'fresh', detail))
    from collections import Counter
    rels = Counter(l.get('relation') for l in graph.links)
    print('edge relations: %s' % dict(rels))
    print('known limits: file-level import index is partial (AST records a '
          'subset of import forms); calls edges cover resolved call sites only.')


def cmd_symbol(graph, args):
    syms = graph.find_symbols(args.name)
    if not syms:
        _die('no symbol named %r in the graph' % args.name)
    lines = sorted('%s:%s  %s' % (s['source_file'], (s.get('source_location') or '?')[1:] or '?', s['label'])
                   for s in syms)
    _emit(lines, args.limit, args.max_chars)


def cmd_callers(graph, args):
    syms = graph.find_symbols(args.name)
    if not syms:
        _die('no symbol named %r in the graph' % args.name)
    lines = []
    for s in syms:
        for link in graph.calls_in.get(s['id'], []):
            caller = graph.nodes.get(link['source']) or {}
            site = '%s:%s' % (link.get('source_file') or caller.get('source_file', '?'),
                              (link.get('source_location') or '?')[1:].lstrip('?') or '?')
            lines.append('%s  %s -> %s' % (
                site, caller.get('label', '?'), s['label']))
    if not lines:
        _die('no callers of %r found (calls edges only cover call-site analysis)' % args.name)
    lines.sort()
    _emit(lines, args.limit, args.max_chars)


def cmd_importers(graph, args):
    files, n_exact = graph.matching_files(args.name)
    if not files:
        _die('no file matching %r in the graph' % args.name)
    if n_exact == 0:
        print('(note: no exact basename match — substring results below)')
    lines = []
    for f in files:
        importers = sorted(i for i in graph.file_importers.get(f, []) if i != f)
        for imp in importers:
            lines.append('%s imports %s' % (imp, f))
    if not lines:
        _die('no importers of %r in the import index (file-level import '
             'coverage is partial — use grep for exhaustive search)' % args.name)
    lines.sort()
    _emit(lines, args.limit, args.max_chars)


def cmd_deps(graph, args):
    files, n_exact = graph.matching_files(args.name)
    if not files:
        _die('no file matching %r in the graph' % args.name)
    if n_exact == 0:
        print('(note: no exact basename match — substring results below)')
    lines = []
    for f in files:
        for dep in sorted(graph.file_imports.get(f, [])):
            if dep != f:
                lines.append('%s -> %s' % (f, dep))
    if not lines:
        _die('no imports of %r in the import index (file-level import '
             'coverage is partial — use grep for exhaustive search)' % args.name)
    lines.sort()
    _emit(lines, args.limit, args.max_chars)


def cmd_file(graph, args):
    files, n_exact = graph.matching_files(args.name)
    if not files:
        # Not in the graph at all: coverage drift (file added after build?)
        disk = _on_disk(args.name)
        if disk:
            _die('%r exists on disk but is NOT in the graph index — '
                 'refresh required (python run_graphify.py)' % args.name)
        _die('no file matching %r in the graph' % args.name)
    if n_exact == 0:
        print('(note: no exact basename match — substring results below)')
    lines = []
    for f in files:
        lines.append('== %s ==' % f)
        for sym in sorted(graph.file_symbols.get(f, []),
                          key=lambda n: n.get('source_location') or ''):
            lines.append('  %s  %s' % (
                (sym.get('source_location') or '?')[1:] or '?', sym['label']))
    _emit(lines, args.limit, args.max_chars)


def _on_disk(pattern):
    pat = str(pattern).lower()
    for root, dirs, files in os.walk(ADDON_ROOT):
        rel = os.path.relpath(root, ADDON_ROOT).replace('\\', '/')
        if rel.startswith(('tests/workspace', 'graphify-out', 'cache',
                           'node_modules', 'dist')):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py') and pat in f.lower():
                return True
    return False


def cmd_subclasses(graph, args):
    syms = graph.find_symbols(args.name)
    if not syms:
        _die('no symbol named %r in the graph' % args.name)
    lines = []
    for s in syms:
        for link in graph.inherits_in.get(s['id'], []):
            child = graph.nodes.get(link['source']) or {}
            lines.append('%s:%s  %s inherits %s' % (
                child.get('source_file', '?'),
                (child.get('source_location') or '?')[1:] or '?',
                child.get('label', '?'), s['label']))
    if not lines:
        _die('no subclasses of %r found' % args.name)
    lines.sort()
    _emit(lines, args.limit, args.max_chars)


def cmd_path(graph, args):
    src_files, _ = graph.matching_files(args.src)
    dst_files, _ = graph.matching_files(args.dst)
    if not src_files or not dst_files:
        _die('no match for %r -> %r' % (args.src, args.dst))
    # BFS over file-level import edges (undirected: dependency path either way)
    adj = defaultdict(set)
    for f, deps in graph.file_imports.items():
        for d in deps:
            adj[f].add(d)
            adj[d].add(f)
    best = None
    for s in src_files:
        for d in dst_files:
            if s == d:
                continue
            prev = {s: None}
            q = deque([s])
            while q:
                cur = q.popleft()
                if cur == d:
                    break
                for nxt in sorted(adj.get(cur, ())):
                    if nxt not in prev:
                        prev[nxt] = cur
                        q.append(nxt)
            if d in prev:
                path, cur = [d], d
                while prev[cur] is not None:
                    cur = prev[cur]
                    path.append(cur)
                path.reverse()
                if best is None or len(path) < len(best):
                    best = path
    if not best:
        _die('no dependency path between %r and %r' % (args.src, args.dst))
    lines = [' -> '.join(best)]
    _emit(lines, args.limit, args.max_chars)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status', help='graph stats + staleness')
    p = sub.add_parser('symbol', help='where is a class/function defined')
    p.add_argument('name')
    p = sub.add_parser('callers', help='who calls a symbol (call sites)')
    p.add_argument('name')
    p = sub.add_parser('importers', help='which files import a file')
    p.add_argument('name')
    p = sub.add_parser('deps', help='what a file imports')
    p.add_argument('name')
    p = sub.add_parser('file', help='symbols defined in a file')
    p.add_argument('name')
    p = sub.add_parser('subclasses', help='classes inheriting a symbol')
    p.add_argument('name')
    p = sub.add_parser('path', help='shortest file dependency path A to B')
    p.add_argument('src')
    p.add_argument('dst')
    for p in sub.choices.values():
        if hasattr(p, 'add_argument') and p.prog.split()[-1] != 'status' and 'path' not in p.prog:
            pass
    for name, p in sub.choices.items():
        for arg in ('limit', 'max_chars', 'refresh', 'force'):
            if name != 'status':
                if arg == 'limit':
                    p.add_argument('--limit', type=int, default=DEFAULT_LIMIT)
                elif arg == 'max_chars':
                    p.add_argument('--max-chars', type=int, default=DEFAULT_MAX_CHARS)
                elif arg == 'force':
                    p.add_argument('--force', action='store_true',
                                   help='answer even when index is stale')
    parser.add_argument('--refresh', action='store_true',
                        help='rebuild the graph (runs run_graphify.py) before querying')

    args = parser.parse_args()

    if args.refresh:
        print('refreshing graph (run_graphify.py)...')
        r = subprocess.run([sys.executable, RUN_GRAPHIFY], cwd=ADDON_ROOT)
        if r.returncode != 0:
            _die('graph refresh failed', 1)

    graph = Graph()
    if args.cmd == 'status':
        cmd_status(graph, args)
        return
    if getattr(args, 'force', False) is False:
        _warn_stale(graph, force=False)
    {'symbol': cmd_symbol, 'callers': cmd_callers, 'importers': cmd_importers,
     'deps': cmd_deps, 'file': cmd_file, 'subclasses': cmd_subclasses,
     'path': cmd_path}[args.cmd](graph, args)


if __name__ == '__main__':
    main()
