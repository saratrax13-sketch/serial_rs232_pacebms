Pace BMS Web UI style fix

This fixes the CSS loading issue under Home Assistant Ingress.

Changed:
- templates/index.html now uses Flask url_for('static', filename='style.css')
- static/style.css remains the visual styling file

Copy these files into your repo and replace the existing ones:
- templates/index.html
- static/style.css

Then:
git add templates/index.html static/style.css
git commit -m "Fix Ingress web UI styling"
git push
