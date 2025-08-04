# 🤖 Git Analyzer: Your AI-Powered GitHub Activity Companion

Hey there! If you're anything like me, you've probably wondered about your own coding habits. How often do you commit? Are those commit messages actually useful? That's exactly why I built **Git Analyzer** – a little desktop app that uses AI to help me (and hopefully you!) get a better handle on our GitHub activity.

This is a personal project, really focused on learning how to dig into my own coding patterns. Fun fact: even the app's look and feel (the GUI) got some design help from AI!

---

## 🎯 What It Does

Here's what Git Analyzer can help you with:

* **Analyze Commit Messages:** Get tips from AI on how to write better, clearer commits.
* **See an Activity Overview:** Track what you've accomplished daily, monthly, or yearly.
* **(Future Goal) Get Code Feedback:** Eventually, I'd love to have the AI analyze code and suggest improvements and best practices.

---

## 🛠️ Tech Stack

| Category          | Technology          |
| :---------------- | :------------------ |
| **GUI Framework** | PyQt5               |
| **AI Integration**| Google Gemini API   |
| **Backend Logic** | Python              |

---

## ⚙️ Configuration

Before you can run the app, you'll need to set up your API keys. The app loads these from a `.env` file in the project's root directory.

1.  **Create the `.env` file:**
    In the `git-analyzer` folder, create a new file named `.env`.

2.  **Add your API keys to the file:**
    Copy and paste the following into your `.env` file, replacing the placeholders with your actual keys.
    ```env
    GITHUB_ACCESS_TOKEN="your_github_token_here"
    GEMINI_API_KEY="your_gemini_api_key_here"
    ```

### How to Get Your API Keys

#### 🔑 GitHub Personal Access Token

You'll need a **classic** token with `repo` and `user` permissions.

1.  Go to your GitHub **Settings**.
2.  Navigate to **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
3.  Click **Generate new token** and select **Generate new token (classic)**.
4.  Give your token a **Note** (e.g., "Git Analyzer App").
5.  Set an **Expiration** period.
6.  Select the following scopes:
    * `repo` (Full control of private repositories)
    * `user` (Access user profile data)
7.  Click **Generate token** and **copy the token immediately**. You won't be able to see it again!

#### ✨ Google Gemini API Key

1.  Go to **Google AI Studio**.
2.  Sign in with your Google account.
3.  Click **Get API key** in the top left corner.
4.  Select **Create API key in new project**.
5.  **Copy your new API key** and add it to your `.env` file.

---

## 🚀 How to Run It

Getting Git Analyzer up and running is pretty straightforward:

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-username/git-analyzer.git](https://github.com/your-username/git-analyzer.git)
    cd git-analyzer
    ```

2.  **Install Requirements:**
    Using a virtual environment is always a good idea here:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the App:**
    Make sure you've completed the **Configuration** steps above first!
    ```bash
    python main.py
    ```

---

I'm pretty excited about where Git Analyzer is headed and plan to add even more AI smarts down the line. If you check it out, feel free to poke around the code, give me some feedback, or even jump in and contribute!