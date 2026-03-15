# Push This Project to GitHub

Repo: **https://github.com/bernardo-heberle/trucking-pay-wizard**

## 1. Use a terminal where Git works

- Open **Git Bash** (from Start menu after installing Git for Windows), or  
- Open **PowerShell** or **Command Prompt** and ensure `git` runs (you may need to restart the terminal after installing Git).

## 2. Save your GitHub login (so you don’t type it every time)

Run once (global for all repos):

```bash
git config --global credential.helper manager
```

On older Windows Git installs you might need:

```bash
git config --global credential.helper wincred
```

Then the **first time** you push (or pull), Git will ask for your GitHub username and password. For the password, use a **Personal Access Token** (not your GitHub account password):

- GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**  
- Generate a token with scope **repo**.  
- Use that token as the “password” when Git prompts you.  
- Git Credential Manager will store it so you won’t be asked again.

## 3. Initialize and push this project

Run these in the project folder (e.g. `cd` into `trucking-pay-wizard`):

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/bernardo-heberle/trucking-pay-wizard.git
git push -u origin main
```

When prompted, use your GitHub username and your **Personal Access Token** as the password. After that, future `git push` / `git pull` will use the stored credentials.

## Optional: GitHub CLI (alternative)

If you prefer, you can use GitHub CLI and then use Git as usual:

```bash
winget install GitHub.cli
gh auth login
```

After `gh auth login`, Git over HTTPS will use the same stored login, so you won’t need to enter it again.
