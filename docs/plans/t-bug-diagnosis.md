# T() Bug Diagnosis

## T() signature

```python
def T(key: str, locale: Optional[str] = None, **kwargs: Any) -> Any:
```

- `key` is a **positional parameter** (first arg)
- `locale` is an optional keyword parameter
- `**kwargs` captures remaining keyword args for string interpolation

## The failing call

**File:** `src/fos/core/experiment/prompt_builder.py`

**Line 162:**
```python
T("experiment.trait_numeric", locale=locale, key=key, value=value, interpretation=interpretation)
```

**Line 164:**
```python
T("experiment.trait_string", locale=locale, key=key, value=value)
```

**Traceback (confirmed):**
```
File "prompt_builder.py", line 162, in build_agent_description
    parts.append(T("experiment.trait_numeric", locale=locale, key=key, value=value, interpretation=interpretation))
TypeError: T() got multiple values for argument 'key'
```

## Root cause

The call sites pass `key=key` as a keyword argument intended for **string interpolation** (the translation template is `"Your {key} score is {value}/100 ({interpretation})."`), but `key` is also the name of T()'s **first positional parameter**. Python sees `"experiment.trait_numeric"` binding to `key` positionally, then `key=key` trying to bind `key` again — hence "multiple values for argument 'key'".

In short: the `**kwargs` variable name `key` collides with the function's positional parameter name `key`.

## Scope

**2 call sites affected** — both in `prompt_builder.py`:

1. `prompt_builder.py:162` — `T("experiment.trait_numeric", ..., key=key, value=value, ...)`
2. `prompt_builder.py:164` — `T("experiment.trait_string", ..., key=key, value=value)`

**Trigger condition:** Agents must have non-identity properties (numeric or string values). The code path is:
- `build_prompt()` → `build_agent_description(agent_properties, ...)` → iterates `meaningful_props` → calls `T()` with `key=key` kwarg

**Not limited to payoff scenarios** — any experiment with agents that have properties triggers this. Payoff scenarios are just the most common case where agents have numeric traits.

**No other T() call sites have this pattern.** Grep for `T(.*key=` across all of `src/fos/` returns only these two lines.

## Translation templates (confirmed)

`src/fos/locales/en.json:1134-1135`:
```json
"trait_numeric": "Your {key} score is {value}/100 ({interpretation}).",
"trait_string": "Your {key} is {value}."
```

`src/fos/locales/zh.json:1134-1135`:
```json
"trait_numeric": "你的{key}得分是{value}/100（{interpretation}）。",
"trait_string": "你的{key}是{value}。"
```

The translation strings use `{key}` as a format placeholder. The callers intended `key=key` to be consumed by `**kwargs` for `.format()` interpolation, not to set the function's `key` parameter.

## Proposed fix

**Option A — Fix the call sites (minimal, safe):**

Rename the format variable from `key` to `trait` in both call sites and translation strings:

```python
# prompt_builder.py:162
T("experiment.trait_numeric", locale=locale, trait=key, value=value, interpretation=interpretation)

# prompt_builder.py:164
T("experiment.trait_string", locale=locale, trait=key, value=value)
```

```json
// en.json
"trait_numeric": "Your {trait} score is {value}/100 ({interpretation}).",
"trait_string": "Your {trait} is {value}."

// zh.json
"trait_numeric": "你的{trait}得分是{value}/100（{interpretation}）。",
"trait_string": "你的{trait}是{value}。"
```

**Option B — Make T()'s key param keyword-only (defensive, broader):**

Change `T(key: str, ...)` to `T(*, key: str, ...)`. This prevents any caller from accidentally passing `key` positionally, but would break ALL existing T() call sites (70+ calls across the codebase).

## Risk

- **Option A (recommended):** Very low risk. Only 2 call sites + 2 translation strings in 2 locale files change. The `key` variable name in the for-loop is unaffected.
- **Option B:** High risk. Would require updating every `T("some.key")` call site to `T(key="some.key")` across the entire codebase.

## Recommended approach

**Option A — fix the call sites and translation templates.** Rename the format variable from `key` to `trait` in:
1. `src/fos/core/experiment/prompt_builder.py` lines 162, 164
2. `src/fos/locales/en.json` lines 1134-1135
3. `src/fos/locales/zh.json` lines 1134-1135

This is a 4-file, 6-line change with no blast radius.
