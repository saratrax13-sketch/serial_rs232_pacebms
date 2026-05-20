# Validation Checklist

Run these checks before release handoff.

## Python Compile

```powershell
python -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
```

## Unit Tests

```powershell
python -m unittest discover -s tests -v
```

## Git Whitespace Check

```powershell
git diff --check
```

Line-ending warnings are acceptable on Windows if there are no actual whitespace errors.

## Config Coverage

```powershell
@'
import yaml
import web_config
with open("config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
options = set((cfg.get("options") or {}).keys())
schema = set((cfg.get("schema") or {}).keys())
groups = []
for keys in web_config.GROUPS.values():
    groups.extend(keys)
group_set = set(groups)
print("options_not_in_schema", sorted(options - schema))
print("schema_not_in_options", sorted(schema - options))
print("options_not_in_groups", sorted(options - group_set - web_config.DEPRECATED_OPTION_KEYS))
print("groups_not_in_options", sorted(group_set - options))
print("duplicate_group_keys", sorted([key for key in group_set if groups.count(key) > 1]))
'@ | python -
```

Expected output:

```text
options_not_in_schema []
schema_not_in_options []
options_not_in_groups []
groups_not_in_options []
duplicate_group_keys []
```

## Serial-First Runtime Files

For runtime validation in a running add-on/container, confirm these exist after the monitor has started and completed at least one valid read:

```sh
ls -lh /data/pacebms-live.json
ls -lh /data/pacebms_metrics.db*
```

The Web UI should be able to read `/api/live` and `/api/history` without MQTT being enabled.

## Documentation Image Links

```powershell
@'
const fs = require("fs");
const path = require("path");
function walk(dir) {
  let out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out = out.concat(walk(p));
    else if (e.name.endsWith(".md")) out.push(p);
  }
  return out;
}
const files = ["README.md", ...walk("docs")];
const missing = [];
for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  const re = /!\[[^\]]*\]\(([^)]+)\)/g;
  let m;
  while ((m = re.exec(text))) {
    const target = decodeURIComponent(m[1]);
    if (/^https?:\/\//.test(target)) continue;
    const full = path.resolve(path.dirname(file), target);
    if (!fs.existsSync(full)) missing.push(`${file}: ${target}`);
  }
}
if (missing.length) {
  console.log(missing.join("\n"));
  process.exit(1);
}
console.log("all_markdown_images_exist");
'@ | node -
```
