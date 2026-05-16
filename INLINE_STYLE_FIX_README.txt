Pace BMS Web UI inline style fix

This removes the dependency on static/style.css and embeds all styling directly in templates/index.html.

Copy this file into your repo:
- templates/index.html

Then bump config.yaml to:
version: "2.0.22"

Add changelog entry for 2.0.22, then:
git add config.yaml CHANGELOG.md templates/index.html
git commit -m "Fix Ingress styling with inline CSS"
git push
