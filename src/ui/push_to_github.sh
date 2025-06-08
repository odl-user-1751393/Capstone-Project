#!/bin/bash

cd "$(dirname "$0")"  # Go to script's directory (ui/)
cd ../../             # Go to root

git add src/ui/index.html
git commit -m "Auto-pushed HTML after user approval"
git push origin user-app
