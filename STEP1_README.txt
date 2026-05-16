Pace BMS Web UI Step 1

This step adds a read-only Home Assistant Ingress web UI.

Copy these into your repo folder:
- web_config.py
- templates/index.html
- static/style.css
- run.sh
- requirements.txt
- config.yaml

Then commit and push:
git add web_config.py templates/index.html static/style.css run.sh requirements.txt config.yaml
git commit -m "Add read-only Home Assistant Ingress web UI"
git push

Then in Home Assistant:
1. Add-on Store -> three dots -> Check for updates
2. Rebuild or update the add-on
3. Start the add-on
4. Open the add-on and click OPEN WEB UI
