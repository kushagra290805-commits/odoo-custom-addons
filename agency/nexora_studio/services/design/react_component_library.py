# -*- coding: utf-8 -*-
"""
React Component Library Synthesizer — Phase 12B Task 2.

Synthesizes a production-ready, modular, composable React component library from the provider-neutral
Component Manifest. Enforces:
1. Variant Intelligence: Dynamic styling and structural layout adaptation based on component variants.
2. Accessibility Metadata Integration: Native semantic HTML (<nav>, <section>, <article>, <header>, <footer>, <dialog>),
   ARIA attributes (aria-label, role, aria-expanded, aria-modal, aria-live), keyboard navigation, and focus states.
3. Design Token Bindings: Direct consumption of CSS variables (var(--...)) mapped from Design System tokens.
4. Composable Hierarchy: Zero duplicated primitive JSX. Molecules and Organisms compose primitives cleanly.
"""
from typing import Dict, Any, List, Optional
from .component_manifest import ComponentManifest, ComponentManifestEntry


class ReactComponentLibrary:
    """
    Synthesizes React JSX project files for all 28 core library components.
    Consumes the framework-agnostic ComponentManifest and InteractionModel.
    """
    def __init__(self, manifest: Optional[ComponentManifest] = None, interaction_model: Optional[Any] = None):
        self.manifest = manifest or ComponentManifest.create_default_manifest()
        self.interaction_model = interaction_model

    def synthesize_all(self) -> Dict[str, str]:

        """
        Generates the complete src/components/ library directory, including all 28 components
        and the index.js barrel exporter.
        """
        files = {}
        # Primitives
        files['src/components/Button.jsx'] = self._gen_button()
        files['src/components/Badge.jsx'] = self._gen_badge()
        files['src/components/Avatar.jsx'] = self._gen_avatar()
        files['src/components/Alert.jsx'] = self._gen_alert()
        files['src/components/Breadcrumb.jsx'] = self._gen_breadcrumb()
        files['src/components/Pagination.jsx'] = self._gen_pagination()
        files['src/components/Modal.jsx'] = self._gen_modal()

        # Molecules
        files['src/components/Card.jsx'] = self._gen_card()
        files['src/components/StatsCard.jsx'] = self._gen_stats_card()
        files['src/components/DashboardCard.jsx'] = self._gen_dashboard_card()
        files['src/components/PricingCard.jsx'] = self._gen_pricing_card()
        files['src/components/Testimonial.jsx'] = self._gen_testimonial()
        files['src/components/BlogCard.jsx'] = self._gen_blog_card()
        files['src/components/ProductCard.jsx'] = self._gen_product_card()
        files['src/components/Accordion.jsx'] = self._gen_accordion()
        files['src/components/Tabs.jsx'] = self._gen_tabs()
        files['src/components/Dropdown.jsx'] = self._gen_dropdown()

        # Organisms
        files['src/components/Navbar.jsx'] = self._gen_navbar()
        files['src/components/Footer.jsx'] = self._gen_footer()
        files['src/components/Hero.jsx'] = self._gen_hero()
        files['src/components/FeatureGrid.jsx'] = self._gen_feature_grid()
        files['src/components/ProductGrid.jsx'] = self._gen_product_grid()
        files['src/components/BlogGrid.jsx'] = self._gen_blog_grid()
        files['src/components/FAQ.jsx'] = self._gen_faq()
        files['src/components/ContactForm.jsx'] = self._gen_contact_form()
        files['src/components/AuthForm.jsx'] = self._gen_auth_form()
        files['src/components/Table.jsx'] = self._gen_table()
        files['src/components/Sidebar.jsx'] = self._gen_sidebar()

        # Barrel exporter
        files['src/components/index.js'] = self._gen_index_js()
        return files

    # =========================================================================
    # 1. Primitives / Atoms
    # =========================================================================
    def _gen_button(self) -> str:
        return '''import React from 'react';
import '../styles/tokens.css';

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  href = null,
  onClick,
  className = '',
  ariaLabel,
  style = {},
  ...props
}) {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: 'var(--font-body, sans-serif)',
    fontWeight: '600',
    borderRadius: 'var(--radius-md, 6px)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    transition: 'all 0.2s ease',
    textDecoration: 'none',
    border: 'none',
    outline: 'none',
    ...style
  };

  const sizeStyles = {
    sm: { padding: '0.375rem 0.75rem', fontSize: '0.875rem' },
    md: { padding: '0.625rem 1.25rem', fontSize: '1rem' },
    lg: { padding: '0.875rem 1.75rem', fontSize: '1.125rem' }
  };

  const variantStyles = {
    primary: { background: 'var(--color-primary, #3b82f6)', color: '#ffffff' },
    secondary: { background: 'var(--color-secondary, #64748b)', color: '#ffffff' },
    outline: { background: 'transparent', border: '1px solid var(--color-primary, #3b82f6)', color: 'var(--color-primary, #3b82f6)' },
    ghost: { background: 'transparent', color: 'var(--color-text, #f8fafc)' },
    link: { background: 'transparent', color: 'var(--color-primary, #3b82f6)', textDecoration: 'underline', padding: 0 }
  };

  const combinedStyle = {
    ...baseStyle,
    ...(sizeStyles[size] || sizeStyles.md),
    ...(variantStyles[variant] || variantStyles.primary)
  };

  if (href && !disabled) {
    return (
      <a
        href={href}
        className={`btn btn-${variant} btn-${size} ${className}`}
        style={combinedStyle}
        role="button"
        aria-label={ariaLabel || (typeof children === 'string' ? children : 'Button link')}
        tabIndex={0}
        {...props}
      >
        {children}
      </a>
    );
  }

  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`btn btn-${variant} btn-${size} ${className}`}
      style={combinedStyle}
      role="button"
      aria-label={ariaLabel || (typeof children === 'string' ? children : 'Action button')}
      aria-disabled={disabled ? 'true' : 'false'}
      tabIndex={disabled ? -1 : 0}
      {...props}
    >
      {children}
    </button>
  );
}'''

    def _gen_badge(self) -> str:
        return '''import React from 'react';

export default function Badge({
  children,
  variant = 'default',
  size = 'sm',
  className = '',
  style = {},
  ...props
}) {
  const variantColors = {
    default: { background: 'var(--color-surface, rgba(255,255,255,0.1))', color: 'var(--color-text, #f8fafc)' },
    success: { background: 'rgba(34,197,94,0.2)', color: '#22c55e' },
    warning: { background: 'rgba(234,179,8,0.2)', color: '#eab308' },
    error: { background: 'rgba(239,68,68,0.2)', color: '#ef4444' },
    info: { background: 'rgba(59,130,246,0.2)', color: '#3b82f6' }
  };

  const badgeStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: size === 'sm' ? '0.25rem 0.625rem' : '0.375rem 0.75rem',
    borderRadius: 'var(--radius-full, 9999px)',
    fontSize: size === 'sm' ? '0.75rem' : '0.875rem',
    fontWeight: '600',
    lineHeight: 1,
    whiteSpace: 'nowrap',
    ...(variantColors[variant] || variantColors.default),
    ...style
  };

  return (
    <span
      className={`badge badge-${variant} ${className}`}
      style={badgeStyle}
      role="status"
      aria-label={`Status: ${typeof children === 'string' ? children : variant}`}
      {...props}
    >
      {children}
    </span>
  );
}'''

    def _gen_avatar(self) -> str:
        return '''import React from 'react';

export default function Avatar({
  src = '',
  alt = 'User Profile Avatar',
  size = 'md',
  fallback = 'U',
  variant = 'circle',
  className = '',
  style = {},
  ...props
}) {
  const sizeMap = { sm: '32px', md: '40px', lg: '56px', xl: '72px' };
  const dim = sizeMap[size] || sizeMap.md;

  const avatarStyle = {
    width: dim,
    height: dim,
    borderRadius: variant === 'circle' ? 'var(--radius-full, 50%)' : 'var(--radius-md, 8px)',
    overflow: 'hidden',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--color-secondary, #64748b)',
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: size === 'sm' ? '0.875rem' : '1.125rem',
    border: '2px solid rgba(255,255,255,0.1)',
    flexShrink: 0,
    ...style
  };

  return (
    <span className={`avatar avatar-${size} ${className}`} style={avatarStyle} role="img" aria-label={alt} {...props}>
      {src ? (
        <img src={src} alt={alt} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        <span>{fallback}</span>
      )}
    </span>
  );
}'''

    def _gen_alert(self) -> str:
        return '''import React from 'react';
import Button from './Button.jsx';

export default function Alert({
  variant = 'info',
  title = '',
  children,
  onClose,
  className = '',
  style = {},
  ...props
}) {
  const variantStyles = {
    info: { borderLeft: '4px solid #3b82f6', background: 'rgba(59,130,246,0.1)' },
    success: { borderLeft: '4px solid #22c55e', background: 'rgba(34,197,94,0.1)' },
    warning: { borderLeft: '4px solid #eab308', background: 'rgba(234,179,8,0.1)' },
    error: { borderLeft: '4px solid #ef4444', background: 'rgba(239,68,68,0.1)' }
  };

  const alertStyle = {
    padding: 'var(--spacing-md, 1rem)',
    borderRadius: 'var(--radius-md, 8px)',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '1rem',
    marginBottom: '1rem',
    ...(variantStyles[variant] || variantStyles.info),
    ...style
  };

  return (
    <div
      className={`alert alert-${variant} ${className}`}
      style={alertStyle}
      role="alert"
      aria-live="polite"
      {...props}
    >
      <div>
        {title && <h4 style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold' }}>{title}</h4>}
        <div style={{ opacity: 0.9 }}>{children}</div>
      </div>
      {onClose && (
        <Button variant="ghost" size="sm" onClick={onClose} ariaLabel="Close alert" style={{ padding: '0.25rem 0.5rem' }}>
          ✕
        </Button>
      )}
    </div>
  );
}'''

    def _gen_breadcrumb(self) -> str:
        return '''import React from 'react';

export default function Breadcrumb({
  items = [],
  separator = '/',
  className = '',
  style = {},
  ...props
}) {
  return (
    <nav
      className={`breadcrumb ${className}`}
      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', ...style }}
      role="navigation"
      aria-label="Breadcrumb"
      {...props}
    >
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        return (
          <React.Fragment key={idx}>
            {isLast ? (
              <span style={{ color: 'var(--color-text, #f8fafc)', fontWeight: 'bold' }} aria-current="page">
                {item.label}
              </span>
            ) : (
              <a href={item.href || '#'} style={{ color: 'var(--color-text-muted, #94a3b8)', textDecoration: 'none' }}>
                {item.label}
              </a>
            )}
            {!isLast && <span style={{ color: 'var(--color-text-muted, #64748b)' }} aria-hidden="true">{separator}</span>}
          </React.Fragment>
        );
      })}
    </nav>
  );
}'''

    def _gen_pagination(self) -> str:
        return '''import React from 'react';
import Button from './Button.jsx';

export default function Pagination({
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  className = '',
  style = {},
  ...props
}) {
  const handlePrev = () => {
    if (currentPage > 1 && onPageChange) onPageChange(currentPage - 1);
  };
  const handleNext = () => {
    if (currentPage < totalPages && onPageChange) onPageChange(currentPage + 1);
  };

  return (
    <nav
      className={`pagination ${className}`}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '2rem', ...style }}
      role="navigation"
      aria-label="Pagination Navigation"
      {...props}
    >
      <Button
        variant="outline"
        size="sm"
        onClick={handlePrev}
        disabled={currentPage <= 1}
        ariaLabel="Go to previous page"
      >
        Previous
      </Button>
      <span style={{ padding: '0 0.5rem', fontSize: '0.875rem' }} aria-current="page">
        Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={handleNext}
        disabled={currentPage >= totalPages}
        ariaLabel="Go to next page"
      >
        Next
      </Button>
    </nav>
  );
}'''

    def _gen_modal(self) -> str:
        return '''import React, { useEffect, useRef } from 'react';
import Card from './Card.jsx';
import Button from './Button.jsx';

export default function Modal({
  isOpen = false,
  title = '',
  onClose,
  children,
  footer,
  variant = 'standard',
  className = '',
  style = {},
  ...props
}) {
  const modalRef = useRef(null);
  const previousFocusRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement;
      if (modalRef.current) {
        modalRef.current.focus();
      }
    } else {
      if (previousFocusRef.current) {
        previousFocusRef.current.focus();
      }
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        if (onClose) onClose();
      } else if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            last.focus();
            e.preventDefault();
          }
        } else {
          if (document.activeElement === last) {
            first.focus();
            e.preventDefault();
          }
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const backdropStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100vw',
    height: '100vh',
    background: 'rgba(0, 0, 0, 0.75)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '1rem'
  };

  const modalWidth = variant === 'fullscreen' ? '100%' : variant === 'drawer' ? '400px' : '500px';

  return (
    <div style={backdropStyle} role="dialog" aria-modal="true" aria-label={title || 'Dialog Modal'} onClick={(e) => { if (e.target === e.currentTarget && onClose) onClose(); }} {...props}>
      <div ref={modalRef} tabIndex={-1} style={{ width: '100%', maxWidth: modalWidth, outline: 'none' }}>
        <Card
          title={title}
          variant="elevated"
          className={`modal-content ${className}`}
          style={{ width: '100%', maxHeight: '90vh', overflowY: 'auto', ...style }}
        >
          <div style={{ marginBottom: '1.5rem' }}>{children}</div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem' }}>
            {footer ? footer : (
              <Button variant="outline" size="sm" onClick={onClose} ariaLabel="Close dialog">
                Close
              </Button>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}'''

    # =========================================================================
    # 2. Molecules (Composing Primitives)
    # =========================================================================
    def _gen_card(self) -> str:
        return '''import React from 'react';
import Badge from './Badge.jsx';
import Avatar from './Avatar.jsx';

export default function Card({
  title = '',
  subtitle = '',
  image = null,
  badge = '',
  avatar = null,
  footer = null,
  children,
  variant = 'elevated',
  onClick,
  className = '',
  style = {},
  ...props
}) {
  const variantStyles = {
    elevated: { background: 'var(--color-surface, rgba(255,255,255,0.05))', boxShadow: 'var(--shadow-md, 0 4px 6px rgba(0,0,0,0.1))', border: '1px solid rgba(255,255,255,0.1)' },
    outlined: { background: 'transparent', border: '1px solid rgba(255,255,255,0.2)' },
    flat: { background: 'var(--color-surface, rgba(255,255,255,0.03))', border: 'none' }
  };

  const cardStyle = {
    borderRadius: 'var(--radius-md, 8px)',
    padding: 'var(--spacing-lg, 1.5rem)',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
    cursor: onClick ? 'pointer' : 'default',
    ...(variantStyles[variant] || variantStyles.elevated),
    ...style
  };

  return (
    <article
      className={`card card-${variant} ${className}`}
      style={cardStyle}
      onClick={onClick}
      role="region"
      aria-label={title || 'Content Card'}
      tabIndex={onClick ? 0 : undefined}
      {...props}
    >
      <div>
        {image && (
          <div style={{ width: '100%', height: '180px', borderRadius: '4px', overflow: 'hidden', marginBottom: '1rem', background: 'rgba(0,0,0,0.2)' }}>
            <img src={image.src || image} alt={image.alt || title || 'Card Media'} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </div>
        )}
        {(title || badge || avatar) && (
          <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {avatar && <Avatar src={avatar.src || avatar} alt={avatar.alt || 'Author Avatar'} size="sm" />}
              <div>
                {title && <h3 style={{ fontSize: '1.25rem', fontWeight: 'bold', margin: 0 }}>{title}</h3>}
                {subtitle && <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted, #94a3b8)', margin: '0.25rem 0 0 0' }}>{subtitle}</p>}
              </div>
            </div>
            {badge && <Badge variant="info">{badge}</Badge>}
          </header>
        )}
        <div style={{ opacity: 0.9 }}>{children}</div>
      </div>
      {footer && (
        <footer style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          {footer}
        </footer>
      )}
    </article>
  );
}'''

    def _gen_stats_card(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';
import Badge from './Badge.jsx';

export default function StatsCard({
  label = '',
  value = '',
  change = '',
  trend = 'neutral',
  className = '',
  style = {},
  ...props
}) {
  const trendBadgeMap = { up: 'success', down: 'error', neutral: 'default' };

  return (
    <Card variant="elevated" className={`stats-card ${className}`} style={{ padding: '1.25rem', ...style }} {...props}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted, #94a3b8)', fontWeight: '500' }}>{label}</span>
        {change && <Badge variant={trendBadgeMap[trend] || 'default'} size="sm">{change}</Badge>}
      </div>
      <div style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--color-text, #f8fafc)' }}>{value}</div>
    </Card>
  );
}'''

    def _gen_dashboard_card(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';
import Button from './Button.jsx';

export default function DashboardCard({
  title = '',
  metric = '',
  description = '',
  actionLabel = '',
  onAction,
  children,
  className = '',
  style = {},
  ...props
}) {
  return (
    <Card
      title={title}
      subtitle={description}
      variant="elevated"
      className={`dashboard-card ${className}`}
      style={{ ...style }}
      footer={
        actionLabel ? (
          <Button variant="outline" size="sm" onClick={onAction} style={{ width: '100%' }}>
            {actionLabel}
          </Button>
        ) : null
      }
      {...props}
    >
      {metric && <div style={{ fontSize: '1.75rem', fontWeight: 'bold', margin: '0.75rem 0' }}>{metric}</div>}
      {children}
    </Card>
  );
}'''

    def _gen_pricing_card(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';
import Badge from './Badge.jsx';
import Button from './Button.jsx';

export default function PricingCard({
  title = 'Starter',
  price = '$29/mo',
  period = 'per month',
  features = [],
  isPopular = false,
  cta = { label: 'Choose Plan', href: '#' },
  className = '',
  style = {},
  ...props
}) {
  const cardVariant = isPopular ? 'elevated' : 'outlined';
  const customStyle = isPopular ? { border: '2px solid var(--color-primary, #3b82f6)', position: 'relative', ...style } : style;

  return (
    <Card
      title={title}
      badge={isPopular ? 'Most Popular' : ''}
      variant={cardVariant}
      className={`pricing-card ${className}`}
      style={{ minWidth: '280px', flex: '1 1 280px', ...customStyle }}
      footer={
        <Button variant={isPopular ? 'primary' : 'outline'} size="lg" href={cta.href} onClick={cta.onClick} style={{ width: '100%' }}>
          {cta.label || 'Get Started'}
        </Button>
      }
      {...props}
    >
      <div style={{ margin: '1.5rem 0' }}>
        <span style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--color-text, #f8fafc)' }}>{price}</span>
        {period && <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted, #94a3b8)', marginLeft: '0.5rem' }}>{period}</span>}
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: '1.5rem 0', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {features.map((feat, idx) => (
          <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.925rem' }}>
            <span style={{ color: 'var(--color-primary, #3b82f6)', fontWeight: 'bold' }}>✓</span>
            <span>{feat}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}'''

    def _gen_testimonial(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';

export default function Testimonial({
  quote = '',
  author = '',
  role = '',
  company = '',
  avatar = '',
  className = '',
  style = {},
  ...props
}) {
  const subtitleStr = [role, company].filter(Boolean).join(' at ');

  return (
    <Card
      title={author}
      subtitle={subtitleStr}
      avatar={avatar ? { src: avatar, alt: author } : null}
      variant="elevated"
      className={`testimonial-card ${className}`}
      style={{ fontStyle: 'italic', ...style }}
      {...props}
    >
      <blockquote style={{ margin: '0 0 1rem 0', fontSize: '1rem', lineHeight: '1.6', opacity: 0.9 }}>
        "{quote}"
      </blockquote>
    </Card>
  );
}'''

    def _gen_blog_card(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';
import Button from './Button.jsx';

export default function BlogCard({
  title = '',
  excerpt = '',
  date = '',
  category = '',
  image = null,
  author = null,
  href = '#',
  className = '',
  style = {},
  ...props
}) {
  return (
    <Card
      title={title}
      subtitle={date}
      image={image}
      badge={category}
      avatar={author ? { src: author.avatar, alt: author.name } : null}
      variant="elevated"
      className={`blog-card ${className}`}
      style={{ ...style }}
      footer={
        <Button variant="link" href={href}>
          Read Article &rarr;
        </Button>
      }
      {...props}
    >
      <p style={{ fontSize: '0.925rem', lineHeight: '1.5', opacity: 0.8, margin: 0 }}>{excerpt}</p>
    </Card>
  );
}'''

    def _gen_product_card(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';
import Button from './Button.jsx';

export default function ProductCard({
  title = '',
  price = '$0.00',
  rating = 5,
  badge = '',
  image = null,
  onAddToCart,
  href = '#',
  className = '',
  style = {},
  ...props
}) {
  return (
    <Card
      title={title}
      image={image}
      badge={badge}
      variant="elevated"
      className={`product-card ${className}`}
      style={{ textAlign: 'center', ...style }}
      footer={
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Button variant="primary" size="sm" onClick={onAddToCart} style={{ flex: 1 }}>
            Add to Cart
          </Button>
          <Button variant="outline" size="sm" href={href}>
            View
          </Button>
        </div>
      }
      {...props}
    >
      <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: 'var(--color-primary, #3b82f6)', margin: '0.5rem 0' }}>
        {price}
      </div>
    </Card>
  );
}'''

    # =========================================================================
    # 3. Organisms (Composing Molecules & Primitives)
    # =========================================================================
    def _gen_navbar(self) -> str:
        return '''import React, { useState } from 'react';
import Button from './Button.jsx';
import Avatar from './Avatar.jsx';

export default function Navbar({
  logo = 'BrandLogo',
  navigation = [],
  actions = [],
  variant = 'standard',
  user = null,
  className = '',
  style = {},
  ...props
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const variantStyles = {
    standard: { background: 'var(--color-background, #0f172a)', borderBottom: '1px solid rgba(255,255,255,0.1)' },
    transparent: { background: 'transparent', borderBottom: 'none', position: 'absolute', width: '100%', zIndex: 50 },
    sidebar: { background: 'var(--color-surface, #1e293b)', borderBottom: '1px solid rgba(255,255,255,0.1)' }
  };

  const navStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 var(--spacing-lg, 2rem)',
    height: '80px',
    width: '100%',
    ...(variantStyles[variant] || variantStyles.standard),
    ...style
  };

  return (
    <header className={`navbar navbar-${variant} ${className}`} style={navStyle} role="banner" {...props}>
      <div style={{ fontWeight: 'bold', fontSize: '1.5rem', color: 'var(--color-text, #f8fafc)' }}>
        <a href="/" style={{ color: 'inherit', textDecoration: 'none' }}>{logo}</a>
      </div>

      <nav role="navigation" aria-label="Main Navigation" style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
        <ul style={{ display: 'flex', gap: '1.5rem', listStyle: 'none', margin: 0, padding: 0 }}>
          {navigation.map((item, idx) => (
            <li key={idx}>
              <a href={item.href || '#'} style={{ color: 'inherit', textDecoration: 'none', fontWeight: '500', fontSize: '0.95rem' }}>
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {actions.map((act, idx) => (
          <Button key={idx} variant={act.variant || 'primary'} size={act.size || 'sm'} href={act.href} onClick={act.onClick}>
            {act.label}
          </Button>
        ))}
        {user && <Avatar src={user.avatar} alt={user.name || 'User'} size="sm" />}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMobileOpen(!mobileOpen)}
          ariaLabel="Toggle mobile navigation menu"
          aria-expanded={mobileOpen ? 'true' : 'false'}
          style={{ display: 'none' }}
        >
          ☰
        </Button>
      </div>
    </header>
  );
}'''

    def _gen_footer(self) -> str:
        return '''import React from 'react';

export default function Footer({
  logo = 'BrandLogo',
  copyright = '© 2026 Nexora Studio. All Rights Reserved.',
  columns = [],
  socials = [],
  className = '',
  style = {},
  ...props
}) {
  const footerStyle = {
    background: 'var(--color-surface, rgba(0,0,0,0.3))',
    borderTop: '1px solid rgba(255,255,255,0.1)',
    padding: 'var(--spacing-2xl, 4rem) var(--spacing-lg, 2rem) var(--spacing-lg, 2rem)',
    marginTop: 'auto',
    width: '100%',
    ...style
  };

  return (
    <footer className={`footer ${className}`} style={footerStyle} role="contentinfo" aria-label="Site Footer" {...props}>
      <div className="container" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '3rem', marginBottom: '3rem' }}>
        <div>
          <div style={{ fontWeight: 'bold', fontSize: '1.5rem', marginBottom: '1rem' }}>{logo}</div>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted, #94a3b8)', lineHeight: '1.6' }}>
            Empowering next-generation web applications with intelligent design systems and provider-neutral architecture.
          </p>
        </div>
        {columns.map((col, idx) => (
          <div key={idx}>
            <h4 style={{ fontSize: '1rem', fontWeight: 'bold', marginBottom: '1rem' }}>{col.title}</h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
              {(col.links || []).map((link, lIdx) => (
                <li key={lIdx}>
                  <a href={link.href || '#'} style={{ color: 'var(--color-text-muted, #94a3b8)', textDecoration: 'none', fontSize: '0.875rem' }}>
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="container" style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted, #64748b)', margin: 0 }}>{copyright}</p>
        {socials && socials.length > 0 && (
          <div style={{ display: 'flex', gap: '1rem' }}>
            {socials.map((soc, idx) => (
              <a key={idx} href={soc.href || '#'} aria-label={soc.label || 'Social Link'} style={{ color: 'inherit', textDecoration: 'none' }}>
                {soc.label}
              </a>
            ))}
          </div>
        )}
      </div>
    </footer>
  );
}'''

    def _gen_hero(self) -> str:
        return '''import React from 'react';
import Badge from './Badge.jsx';
import Button from './Button.jsx';

export default function Hero({
  title = 'Welcome to Our Platform',
  subtitle = 'Deliver state-of-the-art web experiences powered by intelligent design.',
  cta = { label: 'Get Started', href: '#features' },
  image = null,
  badge = '',
  variant = 'centered',
  className = '',
  style = {},
  ...props
}) {
  const isSplit = variant === 'split';
  const isFullscreen = variant === 'fullscreen';

  const heroStyle = {
    padding: isFullscreen ? '0' : 'var(--spacing-2xl, 6rem) 0',
    minHeight: isFullscreen ? '100vh' : 'auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: isSplit ? 'space-between' : 'center',
    flexDirection: isSplit ? 'row' : 'column',
    textAlign: isSplit ? 'left' : 'center',
    gap: '3rem',
    width: '100%',
    ...style
  };

  return (
    <section className={`hero hero-${variant} ${className}`} style={heroStyle} role="region" aria-label="Hero Banner" {...props}>
      <div className="container" style={{ display: 'flex', flexDirection: isSplit ? 'row' : 'column', alignItems: 'center', gap: '3rem', justifyContent: 'space-between', width: '100%' }}>
        <div style={{ flex: 1, maxWidth: isSplit ? '600px' : '800px', margin: isSplit ? '0' : '0 auto' }}>
          {badge && <div style={{ marginBottom: '1.5rem' }}><Badge variant="info" size="md">{badge}</Badge></div>}
          <h1 style={{ fontSize: 'calc(2.5rem + 1.5vw)', fontWeight: '800', lineHeight: '1.15', marginBottom: '1.5rem', color: 'var(--color-text, #f8fafc)' }}>
            {title}
          </h1>
          <p style={{ fontSize: '1.25rem', color: 'var(--color-text-muted, #94a3b8)', lineHeight: '1.6', marginBottom: '2.5rem' }}>
            {subtitle}
          </p>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: isSplit ? 'flex-start' : 'center', flexWrap: 'wrap' }}>
            {cta && (
              <Button variant="primary" size="lg" href={cta.href} onClick={cta.onClick}>
                {cta.label || 'Explore Now'}
              </Button>
            )}
            {props.secondaryCta && (
              <Button variant="outline" size="lg" href={props.secondaryCta.href} onClick={props.secondaryCta.onClick}>
                {props.secondaryCta.label || 'Learn More'}
              </Button>
            )}
          </div>
        </div>
        {image && (
          <div style={{ flex: 1, width: '100%', maxWidth: isSplit ? '550px' : '800px' }}>
            <div style={{ borderRadius: 'var(--radius-lg, 12px)', overflow: 'hidden', boxShadow: 'var(--shadow-lg)', background: 'rgba(255,255,255,0.05)' }}>
              <img src={image.src || image} alt={image.alt || 'Hero Illustration'} style={{ width: '100%', height: 'auto', display: 'block' }} />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}'''

    def _gen_feature_grid(self) -> str:
        return '''import React from 'react';
import Card from './Card.jsx';

export default function FeatureGrid({
  title = 'Key Features',
  subtitle = 'Everything you need to build next-generation web applications.',
  features = [],
  columns = 3,
  className = '',
  style = {},
  ...props
}) {
  return (
    <section className={`feature-grid ${className}`} style={{ padding: 'var(--spacing-2xl, 5rem) 0', width: '100%', ...style }} role="region" aria-label="Features Grid" {...props}>
      <div className="container">
        {(title || subtitle) && (
          <header style={{ textAlign: 'center', maxWidth: '700px', margin: '0 auto 3.5rem auto' }}>
            {title && <h2 style={{ fontSize: '2.25rem', fontWeight: 'bold', marginBottom: '1rem' }}>{title}</h2>}
            {subtitle && <p style={{ fontSize: '1.125rem', color: 'var(--color-text-muted, #94a3b8)', margin: 0 }}>{subtitle}</p>}
          </header>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(${columns === 4 ? '220px' : '280px'}, 1fr))`, gap: '2rem' }}>
          {features.map((feat, idx) => (
            <Card key={idx} title={feat.title} subtitle={feat.subtitle} variant="elevated">
              <p style={{ fontSize: '0.95rem', color: 'var(--color-text-muted, #94a3b8)', margin: 0, lineHeight: 1.6 }}>
                {feat.description}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}'''

    def _gen_product_grid(self) -> str:
        return '''import React from 'react';
import ProductCard from './ProductCard.jsx';

export default function ProductGrid({
  title = 'Featured Products',
  products = [],
  columns = 4,
  className = '',
  style = {},
  ...props
}) {
  return (
    <section className={`product-grid ${className}`} style={{ padding: 'var(--spacing-2xl, 4rem) 0', width: '100%', ...style }} role="region" aria-label="Product Catalog Grid" {...props}>
      <div className="container">
        {title && <h2 style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '2.5rem', textAlign: 'center' }}>{title}</h2>}
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(240px, 1fr))`, gap: '2rem' }}>
          {products.map((prod, idx) => (
            <ProductCard
              key={idx}
              title={prod.title}
              price={prod.price}
              badge={prod.badge}
              image={prod.image}
              onAddToCart={prod.onAddToCart}
              href={prod.href}
            />
          ))}
        </div>
      </div>
    </section>
  );
}'''

    def _gen_blog_grid(self) -> str:
        return '''import React from 'react';
import BlogCard from './BlogCard.jsx';

export default function BlogGrid({
  title = 'Latest Insights',
  posts = [],
  columns = 3,
  className = '',
  style = {},
  ...props
}) {
  return (
    <section className={`blog-grid ${className}`} style={{ padding: 'var(--spacing-2xl, 4rem) 0', width: '100%', ...style }} role="feed" aria-label="Blog Articles Feed" {...props}>
      <div className="container">
        {title && <h2 style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '2.5rem', textAlign: 'center' }}>{title}</h2>}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
          {posts.map((post, idx) => (
            <BlogCard
              key={idx}
              title={post.title}
              excerpt={post.excerpt}
              date={post.date}
              category={post.category}
              image={post.image}
              author={post.author}
              href={post.href}
            />
          ))}
        </div>
      </div>
    </section>
  );
}'''

    def _gen_faq(self) -> str:
        return '''import React, { useState } from 'react';
import Card from './Card.jsx';

export default function FAQ({
  title = 'Frequently Asked Questions',
  subtitle = 'Everything you need to know about our product and billing.',
  items = [],
  className = '',
  style = {},
  ...props
}) {
  const [openIdx, setOpenIdx] = useState(null);

  const toggleItem = (idx) => {
    setOpenIdx(openIdx === idx ? null : idx);
  };

  return (
    <section className={`faq-section ${className}`} style={{ padding: 'var(--spacing-2xl, 5rem) 0', width: '100%', ...style }} role="region" aria-label="Frequently Asked Questions" {...props}>
      <div className="container" style={{ maxWidth: '800px', margin: '0 auto' }}>
        {(title || subtitle) && (
          <header style={{ textAlign: 'center', marginBottom: '3rem' }}>
            {title && <h2 style={{ fontSize: '2.25rem', fontWeight: 'bold', marginBottom: '1rem' }}>{title}</h2>}
            {subtitle && <p style={{ fontSize: '1.125rem', color: 'var(--color-text-muted, #94a3b8)' }}>{subtitle}</p>}
          </header>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {items.map((item, idx) => {
            const isOpen = openIdx === idx;
            return (
              <Card key={idx} variant="elevated" style={{ padding: '1.25rem 1.5rem', cursor: 'pointer' }} onClick={() => toggleItem(idx)}>
                <button
                  type="button"
                  style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'transparent', border: 'none', color: 'inherit', font: 'inherit', fontWeight: 'bold', fontSize: '1.1rem', cursor: 'pointer', textAlign: 'left', padding: 0 }}
                  aria-expanded={isOpen ? 'true' : 'false'}
                  aria-controls={`faq-answer-${idx}`}
                >
                  <span>{item.question}</span>
                  <span style={{ fontSize: '1.5rem', transition: 'transform 0.2s ease', transform: isOpen ? 'rotate(45deg)' : 'none' }}>+</span>
                </button>
                {isOpen && (
                  <div id={`faq-answer-${idx}`} style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.08)', color: 'var(--color-text-muted, #94a3b8)', lineHeight: 1.6 }}>
                    {item.answer}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}'''

    def _gen_contact_form(self) -> str:
        return '''import React, { useState } from 'react';
import Card from './Card.jsx';
import Button from './Button.jsx';
import Alert from './Alert.jsx';

export default function ContactForm({
  title = 'Get in Touch',
  subtitle = 'We would love to hear from you. Please fill out the form below.',
  submitLabel = 'Send Message',
  onSubmit,
  className = '',
  style = {},
  ...props
}) {
  const [status, setStatus] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    setStatus('success');
    if (onSubmit) onSubmit(e);
  };

  return (
    <section className={`contact-form-section ${className}`} style={{ padding: 'var(--spacing-2xl, 5rem) 0', width: '100%', ...style }} role="region" aria-label="Contact Inquiry Form" {...props}>
      <div className="container" style={{ maxWidth: '600px', margin: '0 auto' }}>
        <Card title={title} subtitle={subtitle} variant="elevated" style={{ padding: '2.5rem' }}>
          {status === 'success' && (
            <Alert variant="success" title="Message Sent!" onClose={() => setStatus(null)}>
              Thank you for contacting us. We will get back to you shortly.
            </Alert>
          )}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '1.5rem' }}>
            <div>
              <label htmlFor="contact-name" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Your Name</label>
              <input id="contact-name" type="text" required placeholder="John Doe" style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md, 6px)', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'var(--color-text, #fff)' }} />
            </div>
            <div>
              <label htmlFor="contact-email" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Email Address</label>
              <input id="contact-email" type="email" required placeholder="john@example.com" style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md, 6px)', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'var(--color-text, #fff)' }} />
            </div>
            <div>
              <label htmlFor="contact-message" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Message</label>
              <textarea id="contact-message" rows={4} required placeholder="How can we help you?" style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md, 6px)', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'var(--color-text, #fff)' }} />
            </div>
            <Button variant="primary" size="lg" type="submit" style={{ width: '100%', marginTop: '0.5rem' }}>
              {submitLabel}
            </Button>
          </form>
        </Card>
      </div>
    </section>
  );
}'''

    def _gen_auth_form(self) -> str:
        return '''import React, { useState } from 'react';
import Card from './Card.jsx';
import Button from './Button.jsx';
import Alert from './Alert.jsx';

export default function AuthForm({
  title = 'Sign In to Account',
  subtitle = 'Enter your credentials below to access your workspace.',
  type = 'login',
  oauthProviders = ['Google', 'GitHub'],
  onSubmit,
  className = '',
  style = {},
  ...props
}) {
  const [error, setError] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit) onSubmit(e);
  };

  return (
    <section className={`auth-form-section ${className}`} style={{ padding: 'var(--spacing-2xl, 5rem) 0', width: '100%', ...style }} role="region" aria-label="Authentication Form" {...props}>
      <div className="container" style={{ maxWidth: '440px', margin: '0 auto' }}>
        <Card title={title} subtitle={subtitle} variant="elevated" style={{ padding: '2.5rem' }}>
          {error && <Alert variant="error" title="Authentication Error" onClose={() => setError(null)}>{error}</Alert>}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '1.5rem' }}>
            <div>
              <label htmlFor="auth-email" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Email Address</label>
              <input id="auth-email" type="email" required placeholder="you@example.com" style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md, 6px)', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'var(--color-text, #fff)' }} />
            </div>
            <div>
              <label htmlFor="auth-password" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Password</label>
              <input id="auth-password" type="password" required placeholder="••••••••" style={{ width: '100%', padding: '0.75rem', borderRadius: 'var(--radius-md, 6px)', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'var(--color-text, #fff)' }} />
            </div>
            <Button variant="primary" size="lg" type="submit" style={{ width: '100%', marginTop: '0.5rem' }}>
              {type === 'login' ? 'Sign In' : 'Create Account'}
            </Button>
          </form>
          {oauthProviders && oauthProviders.length > 0 && (
            <div style={{ marginTop: '2rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1.5rem', textAlign: 'center' }}>
              <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted, #94a3b8)', marginBottom: '1rem' }}>Or continue with</p>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                {oauthProviders.map((prov, idx) => (
                  <Button key={idx} variant="outline" size="sm" style={{ flex: 1 }}>
                    {prov}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </section>
  );
}'''

    def _gen_table(self) -> str:
        return '''import React, { useState } from 'react';
import Badge from './Badge.jsx';
import Button from './Button.jsx';
import Pagination from './Pagination.jsx';

export default function Table({
  columns = [],
  data = [],
  pagination = null,
  variant = 'standard',
  className = '',
  style = {},
  ...props
}) {
  const [page, setPage] = useState(1);
  const rowsPerPage = pagination?.pageSize || 10;
  const totalRows = data.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage) || 1;

  const currentData = pagination ? data.slice((page - 1) * rowsPerPage, page * rowsPerPage) : data;

  return (
    <div className={`table-wrapper table-${variant} ${className}`} style={{ width: '100%', overflowX: 'auto', ...style }} role="region" aria-label="Data Grid Table" {...props}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.95rem' }} role="table">
        <thead>
          <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)' }}>
            {columns.map((col, idx) => (
              <th key={idx} scope="col" style={{ padding: '0.875rem 1rem', fontWeight: '700', color: 'var(--color-text, #f8fafc)' }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {currentData.map((row, rIdx) => (
            <tr key={rIdx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.15s ease' }}>
              {columns.map((col, cIdx) => (
                <td key={cIdx} style={{ padding: '0.875rem 1rem', color: 'var(--color-text-muted, #cbd5e1)' }}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {pagination && totalPages > 1 && (
        <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
      )}
    </div>
  );
}'''

    def _gen_sidebar(self) -> str:
        return '''import React from 'react';
import Button from './Button.jsx';
import Badge from './Badge.jsx';
import Avatar from './Avatar.jsx';

export default function Sidebar({
  items = [],
  activeItem = '',
  collapsed = false,
  onToggle,
  user = null,
  className = '',
  style = {},
  ...props
}) {
  const sidebarWidth = collapsed ? '80px' : '260px';

  const sidebarStyle = {
    width: sidebarWidth,
    minHeight: '100vh',
    background: 'var(--color-surface, #1e293b)',
    borderRight: '1px solid rgba(255,255,255,0.1)',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    padding: '1.5rem 1rem',
    transition: 'width 0.2s ease',
    flexShrink: 0,
    ...style
  };

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''} ${className}`} style={sidebarStyle} role="complementary" aria-label="Sidebar NavigationDrawer" {...props}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'space-between', marginBottom: '2.5rem', padding: '0 0.5rem' }}>
          {!collapsed && <span style={{ fontWeight: 'bold', fontSize: '1.25rem', color: 'var(--color-text, #fff)' }}>Nexora</span>}
          {onToggle && (
            <Button variant="ghost" size="sm" onClick={onToggle} ariaLabel="Toggle sidebar collapse" style={{ padding: '0.25rem 0.5rem' }}>
              {collapsed ? '→' : '←'}
            </Button>
          )}
        </div>
        <nav role="navigation" aria-label="Sidebar Menu">
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {items.map((item, idx) => {
              const isActive = activeItem === (item.key || item.label);
              return (
                <li key={idx}>
                  <a
                    href={item.href || '#'}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: collapsed ? 'center' : 'space-between',
                      padding: '0.75rem 1rem',
                      borderRadius: 'var(--radius-md, 6px)',
                      background: isActive ? 'var(--color-primary, #3b82f6)' : 'transparent',
                      color: isActive ? '#fff' : 'var(--color-text-muted, #94a3b8)',
                      textDecoration: 'none',
                      fontWeight: isActive ? '600' : '500',
                      transition: 'all 0.15s ease'
                    }}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      {item.icon && <span>{item.icon}</span>}
                      {!collapsed && <span>{item.label}</span>}
                    </div>
                    {!collapsed && item.badge && <Badge variant="info" size="sm">{item.badge}</Badge>}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
      {user && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', justifyContent: collapsed ? 'center' : 'flex-start' }}>
          <Avatar src={user.avatar} alt={user.name || 'User'} size="md" />
          {!collapsed && (
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontWeight: '600', fontSize: '0.9rem', color: 'var(--color-text, #fff)', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{user.name}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #64748b)' }}>{user.role || 'Member'}</div>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}'''

    def _gen_accordion(self) -> str:
        return '''import React, { useState } from 'react';

export default function Accordion({
  items = [],
  defaultExpanded = -1,
  allowMultiple = false,
  onToggle,
  className = '',
  style = {},
  ...props
}) {
  const [expanded, setExpanded] = useState(allowMultiple ? [] : defaultExpanded);

  const handleToggle = (idx) => {
    if (allowMultiple) {
      setExpanded((prev) =>
        prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]
      );
    } else {
      setExpanded((prev) => (prev === idx ? -1 : idx));
    }
    if (onToggle) onToggle(idx);
  };

  const isItemExpanded = (idx) =>
    allowMultiple ? expanded.includes(idx) : expanded === idx;

  const handleKeyDown = (e, idx) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleToggle(idx);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextBtn = document.getElementById(`accordion-header-${(idx + 1) % items.length}`);
      if (nextBtn) nextBtn.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevBtn = document.getElementById(`accordion-header-${(idx - 1 + items.length) % items.length}`);
      if (prevBtn) prevBtn.focus();
    }
  };

  return (
    <div className={`accordion ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%', ...style }} role="region" aria-label="Accordion Group" {...props}>
      {items.map((item, idx) => {
        const open = isItemExpanded(idx);
        return (
          <div key={idx} style={{ border: '1px solid var(--color-border, #334155)', borderRadius: 'var(--radius-md, 8px)', overflow: 'hidden', background: 'var(--color-bg-card, #1e293b)' }}>
            <button
              type="button"
              id={`accordion-header-${idx}`}
              aria-expanded={open ? 'true' : 'false'}
              aria-controls={`accordion-panel-${idx}`}
              onClick={() => handleToggle(idx)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', background: 'transparent', border: 'none', color: 'var(--color-text, #fff)', fontWeight: 'bold', fontSize: '1rem', cursor: 'pointer', textAlign: 'left', outline: 'none' }}
            >
              <span>{item.title}</span>
              <span aria-hidden="true" style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}>▼</span>
            </button>
            {open && (
              <div id={`accordion-panel-${idx}`} role="region" aria-labelledby={`accordion-header-${idx}`} style={{ padding: '1rem 1.25rem', borderTop: '1px solid var(--color-border, #334155)', color: 'var(--color-text-muted, #94a3b8)', lineHeight: 1.6 }}>
                {item.content}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}'''

    def _gen_tabs(self) -> str:
        return '''import React, { useState } from 'react';

export default function Tabs({
  tabs = [],
  defaultTab = 0,
  onChange,
  className = '',
  style = {},
  ...props
}) {
  const [activeTab, setActiveTab] = useState(defaultTab);

  const handleSelect = (idx) => {
    setActiveTab(idx);
    if (onChange) onChange(idx);
  };

  const handleKeyDown = (e, idx) => {
    let nextIdx = idx;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      nextIdx = (idx + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      nextIdx = (idx - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIdx = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIdx = tabs.length - 1;
    } else {
      return;
    }
    handleSelect(nextIdx);
    const targetTab = document.getElementById(`tab-btn-${nextIdx}`);
    if (targetTab) targetTab.focus();
  };

  return (
    <div className={`tabs-container ${className}`} style={{ width: '100%', ...style }} {...props}>
      <div role="tablist" aria-label="Content Tabs" style={{ display: 'flex', borderBottom: '2px solid var(--color-border, #334155)', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {tabs.map((tab, idx) => {
          const isSelected = activeTab === idx;
          return (
            <button
              key={idx}
              type="button"
              id={`tab-btn-${idx}`}
              role="tab"
              aria-selected={isSelected ? 'true' : 'false'}
              aria-controls={`tab-panel-${idx}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => handleSelect(idx)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              style={{ padding: '0.75rem 1.25rem', background: 'transparent', border: 'none', borderBottom: isSelected ? '2px solid var(--color-primary, #3b82f6)' : '2px solid transparent', color: isSelected ? 'var(--color-primary, #3b82f6)' : 'var(--color-text-muted, #94a3b8)', fontWeight: isSelected ? 'bold' : 'normal', cursor: 'pointer', outline: 'none', transition: 'all 0.2s ease', marginBottom: '-2px' }}
            >
              {tab.label || tab.title}
            </button>
          );
        })}
      </div>
      {tabs.map((tab, idx) => {
        if (activeTab !== idx) return null;
        return (
          <div key={idx} id={`tab-panel-${idx}`} role="tabpanel" aria-labelledby={`tab-btn-${idx}`} tabIndex={0} style={{ outline: 'none', color: 'var(--color-text, #fff)' }}>
            {tab.content}
          </div>
        );
      })}
    </div>
  );
}'''

    def _gen_dropdown(self) -> str:
        return '''import React, { useState, useRef, useEffect } from 'react';

export default function Dropdown({
  label = 'Select Option',
  options = [],
  onSelect,
  className = '',
  style = {},
  ...props
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const toggleOpen = () => {
    setIsOpen(!isOpen);
    if (!isOpen) setFocusedIndex(0);
  };

  const handleOptionSelect = (option, idx) => {
    setIsOpen(false);
    if (onSelect) onSelect(option, idx);
    if (triggerRef.current) triggerRef.current.focus();
  };

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        menuRef.current && !menuRef.current.contains(e.target)
      ) {
        if (isOpen) {
          setIsOpen(false);
          if (triggerRef.current) triggerRef.current.focus();
        }
      }
    };
    const handleGlobalKeyDown = (e) => {
      if (isOpen && e.key === 'Escape') {
        e.preventDefault();
        setIsOpen(false);
        if (triggerRef.current) triggerRef.current.focus();
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleGlobalKeyDown);
    };
  }, [isOpen]);

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setIsOpen(true);
        setFocusedIndex(0);
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev + 1) % options.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev - 1 + options.length) % options.length);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < options.length) {
        handleOptionSelect(options[focusedIndex], focusedIndex);
      }
    }
  };

  return (
    <div className={`dropdown-container ${className}`} style={{ position: 'relative', display: 'inline-block', ...style }} onKeyDown={handleKeyDown} {...props}>
      <button
        type="button"
        ref={triggerRef}
        aria-haspopup="listbox"
        aria-expanded={isOpen ? 'true' : 'false'}
        aria-controls="dropdown-menu"
        onClick={toggleOpen}
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 1rem', background: 'var(--color-bg-card, #1e293b)', border: '1px solid var(--color-border, #334155)', borderRadius: 'var(--radius-md, 6px)', color: 'var(--color-text, #fff)', cursor: 'pointer', fontWeight: '500', outline: 'none' }}
      >
        <span>{label}</span>
        <span aria-hidden="true" style={{ fontSize: '0.75rem', transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}>▼</span>
      </button>
      {isOpen && (
        <ul
          ref={menuRef}
          id="dropdown-menu"
          role="listbox"
          style={{ position: 'absolute', top: '100%', left: 0, marginTop: '0.25rem', minWidth: '180px', background: 'var(--color-bg-card, #1e293b)', border: '1px solid var(--color-border, #334155)', borderRadius: 'var(--radius-md, 6px)', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.5)', zIndex: 50, padding: '0.25rem 0', listStyle: 'none', margin: '0.25rem 0 0 0' }}
        >
          {options.map((option, idx) => {
            const isFocused = focusedIndex === idx;
            return (
              <li
                key={idx}
                role="option"
                aria-selected={isFocused ? 'true' : 'false'}
                onClick={() => handleOptionSelect(option, idx)}
                style={{ padding: '0.5rem 1rem', cursor: 'pointer', background: isFocused ? 'var(--color-primary, #3b82f6)' : 'transparent', color: isFocused ? '#fff' : 'var(--color-text, #cbd5e1)', transition: 'background 0.15s ease' }}
              >
                {option.label || option.title}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}'''

    # =========================================================================
    # 4. Barrel Exporter (src/components/index.js)
    # =========================================================================
    def _gen_index_js(self) -> str:
        return '''// Production React Component Library — Synthesized by Nexora Engine (Phase 12B)
// Reusable primitive, molecule, and organism exports.

// Primitives
export { default as Button } from './Button.jsx';
export { default as Badge } from './Badge.jsx';
export { default as Avatar } from './Avatar.jsx';
export { default as Alert } from './Alert.jsx';
export { default as Breadcrumb } from './Breadcrumb.jsx';
export { default as Pagination } from './Pagination.jsx';
export { default as Modal } from './Modal.jsx';

// Molecules
export { default as Card } from './Card.jsx';
export { default as StatsCard } from './StatsCard.jsx';
export { default as DashboardCard } from './DashboardCard.jsx';
export { default as PricingCard } from './PricingCard.jsx';
export { default as Testimonial } from './Testimonial.jsx';
export { default as BlogCard } from './BlogCard.jsx';
export { default as ProductCard } from './ProductCard.jsx';
export { default as Accordion } from './Accordion.jsx';
export { default as Tabs } from './Tabs.jsx';
export { default as Dropdown } from './Dropdown.jsx';

// Organisms
export { default as Navbar } from './Navbar.jsx';
export { default as Footer } from './Footer.jsx';
export { default as Hero } from './Hero.jsx';
export { default as FeatureGrid } from './FeatureGrid.jsx';
export { default as ProductGrid } from './ProductGrid.jsx';
export { default as BlogGrid } from './BlogGrid.jsx';
export { default as FAQ } from './FAQ.jsx';
export { default as ContactForm } from './ContactForm.jsx';
export { default as AuthForm } from './AuthForm.jsx';
export { default as Table } from './Table.jsx';
export { default as Sidebar } from './Sidebar.jsx';
'''

