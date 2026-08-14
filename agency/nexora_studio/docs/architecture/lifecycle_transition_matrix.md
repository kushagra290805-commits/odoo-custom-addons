# Lifecycle Transition Audit

## Transition Verification

The following matrix represents the valid transitions enforced by the `ConnectorLifecycleStateMachine`.

| State | Allowed Target States | Terminal? | Unreachable? |
| :--- | :--- | :--- | :--- |
| `REGISTERED` | `DISCOVERED`, `FAILED`, `REMOVED` | No | No |
| `DISCOVERED` | `DOWNLOADED`, `INSTALLED`, `FAILED`, `REGISTERED` | No | No |
| `DOWNLOADED` | `INSTALLED`, `FAILED`, `DISCOVERED` | No | No |
| `INSTALLED` | `CONFIGURED`, `FAILED`, `DISCOVERED` | No | No |
| `CONFIGURED` | `AUTHENTICATED`, `VALIDATED`, `FAILED`, `INSTALLED` | No | No |
| `AUTHENTICATED`| `VALIDATED`, `FAILED`, `CONFIGURED` | No | No |
| `VALIDATED` | `HEALTHY`, `FAILED`, `AUTHENTICATED` | No | No |
| `HEALTHY` | `RUNNING`, `FAILED`, `DISABLED` | No | No |
| `RUNNING` | `PAUSED`, `FAILED`, `DISABLED`, `UPDATING`, `HEALTHY` | No | No |
| `PAUSED` | `RUNNING`, `DISABLED`, `FAILED` | No | No |
| `FAILED` | `DISCOVERED`, `INSTALLED`, `CONFIGURED`, `DISABLED`, `REMOVED` | No | No |
| `UPDATING` | `INSTALLED`, `FAILED` | No | No |
| `DISABLED` | `CONFIGURED`, `REMOVED` | No | No |
| `REMOVED` | (None) | Yes | No |

## Audit Results
- **Every state reachable**: PASSED.
- **Every terminal state terminal**: PASSED. `REMOVED` has no outbound edges.
- **No orphan states**: PASSED. All states are connected in the digraph.
- **No impossible transitions**: PASSED.

✅ **PASSED**.
