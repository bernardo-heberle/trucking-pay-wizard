# Trucking Pay Wizard — Installation Guide

Follow these steps to install and set up the Trucking Pay Wizard on your
Windows computer.  You only need to do this once.

---

## Step 1 — Download the installer

1. Go to the download link provided by your supervisor:
   [https://github.com/bernardo-heberle/trucking-pay-wizard-releases/releases/latest](https://github.com/bernardo-heberle/trucking-pay-wizard-releases/releases/latest)
2. Under **Assets**, click **TruckingPayWizardSetup.exe** to download it.
3. Save the file somewhere easy to find (your Desktop is fine).

---

## Step 2 — Run the installer

1. Double-click **TruckingPayWizardSetup.exe**.
2. **Windows SmartScreen may appear** with the message
   *"Windows protected your PC"*.  This is normal for new software — click
   **More info**, then **Run anyway**.

   ![SmartScreen click-through: More info → Run anyway]

3. Follow the short installer wizard:
   - Accept the default install folder (or choose your own).
   - Optionally tick **Create a desktop shortcut**.
   - Click **Install**, then **Finish**.

The app will open automatically when the installer finishes.

---

## Step 3 — Enter your setup code

On first launch you will see the **API Credentials Setup** screen.

Your IT contact or supervisor will have sent you a **setup code** — a long
string of letters and numbers.

1. Paste that code into the **"Have a setup code?"** box.
2. Click **Use code** — the three fields below will fill in automatically.
3. Click **Save & Continue**.

The app will test your credentials.  If anything is wrong, a red message will
appear under the relevant field — contact your IT contact or supervisor for
a corrected setup code.

If you did **not** receive a setup code, fill in the three fields manually:
- **Anthropic API key** — starts with `sk-ant-`
- **Azure endpoint** — starts with `https://` and ends with `.cognitiveservices.azure.com/`
- **Azure Document Intelligence key** — a 32-character string

Once both services pass their tests, you will go straight to the main screen.

---

## Step 4 — Process your first claim

1. Collect all income documents for a claim into a single folder on your
   computer (or a shared drive).
2. In the app, click **Get Started →** on the welcome screen.
3. Click **Browse…** and select that folder.
   - Alternatively, drag the document files directly onto the app window.
4. Type a file name for your report (for example `claim_123`).
5. Click **Generate Report**.

The app will read every document, extract the key figures, and produce two
files in a **results** sub-folder:

| File | What it is |
|------|-----------|
| `claim_123_combined.pdf` | All your documents in one PDF, easy to attach to a claim |
| `claim_123_extracted.xlsx` | One row per document — gross pay, net pay, payment dates |

---

## Using the app day-to-day

- **Run the app again on the same folder** to add new documents — already
  processed documents are skipped automatically.
- **Open in Explorer** button (next to the folder field) opens the working
  folder in Windows Explorer if you need to add or review files.

---

## Keeping the app up to date

The app checks for updates in the background once per day.  When a new
version is available, a small dialog will appear offering to install it.

Click **Install now** — the app will update itself silently and reopen on the
new version.  Your credentials are preserved across updates.

You can also manually check via **File → Check for updates…**

---

## Changing your credentials

If your API keys change (e.g. a key is rotated by IT), go to
**File → Update keys…** and enter the new setup code or values.

---

## Reporting a problem

If something goes wrong:

1. Go to **File → Report an issue…**
2. The app will save a log file bundle to your Desktop and open your email
   client with a pre-filled message.
3. Attach the `.zip` file from your Desktop and click Send.

Your IT contact or the tool's developer will use the log file to investigate.

---

## Uninstalling

Go to **Settings → Apps** (or **Control Panel → Programs and Features**),
find **Trucking Pay Wizard**, and click **Uninstall**.

Your credentials stored in Windows Credential Manager are **not** removed —
if you reinstall the app you will not need to enter the setup code again.
