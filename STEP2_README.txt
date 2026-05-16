Pace BMS Web UI Step 2 - Live Status

This adds a Live Status section to the read-only Home Assistant Ingress page.

Copy these files into your repo:
- web_config.py
- templates/index.html

Then bump config.yaml to:
version: "2.0.23"

Add a changelog entry for 2.0.23.

Commit and push:
git add web_config.py templates/index.html config.yaml CHANGELOG.md
git commit -m "Add live MQTT status to web UI"
git push

Then update/rebuild the add-on in Home Assistant and restart it.
