#!/bin/zsh

set -e

PROJECT_DIR="/Users/darkcreation/Documents/git_repos/prompt-study-notifier"
APP_DIR="${HOME}/Applications/Prompt Study Notifier.app"
LAUNCHER_SCRIPT="${PROJECT_DIR}/scripts/launch_prompt_study_notifier.sh"

mkdir -p "${HOME}/Applications"
rm -rf "${APP_DIR}"

chmod +x "${LAUNCHER_SCRIPT}"
/usr/bin/osacompile -o "${APP_DIR}" -e "do shell script quoted form of \"${LAUNCHER_SCRIPT}\""

echo "Installed ${APP_DIR}"
echo "Open it from Spotlight by searching for: Prompt Study Notifier"
