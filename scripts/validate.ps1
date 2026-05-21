param(
    [switch]$SkipTests,
    [switch]$SkipImages
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "== $Name =="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "Python compile" {
    python -B -m py_compile `
        bms_monitor.py `
        bms_notify.py `
        web_config.py `
        constants.py `
        supervisor.py `
        tests\test_core_behaviour.py `
        battery_profiles.py `
        bms_live.py `
        bms_history.py `
        standalone_config.py
}

if (-not $SkipTests) {
    Invoke-Step "Unit tests" {
        python -m unittest discover -s tests -v
    }
}

Invoke-Step "Config coverage" {
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

checks = {
    "options_not_in_schema": sorted(options - schema),
    "schema_not_in_options": sorted(schema - options),
    "options_not_in_groups": sorted(options - group_set - web_config.DEPRECATED_OPTION_KEYS),
    "groups_not_in_options": sorted(group_set - options),
    "duplicate_group_keys": sorted([key for key in group_set if groups.count(key) > 1]),
}

failed = False
for name, values in checks.items():
    print(name, values)
    if values:
        failed = True

if failed:
    raise SystemExit(1)
'@ | python -
}

if (-not $SkipImages) {
    Invoke-Step "Markdown image links" {
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
    }
}

Invoke-Step "Git whitespace" {
    git diff --check
}

Write-Host ""
Write-Host "Validation passed."
