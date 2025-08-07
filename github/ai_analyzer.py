from google import genai
# import google.generativeai as genai
from google.genai import types
from decouple import config
from icecream import ic

API_KEY = config("GEMINI_API_TOKEN")

client = genai.Client(api_key=API_KEY)


def generate_ai_response(prompt:str) -> str:
    """A helper function to create AI respones with the entered prompts"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
            ),
        )

        return response.text.strip()
    except Exception as e:
        # The SDK will raise specific errors, but a general catch-all is fine for now
        print(f"An error occurred while calling the Gemini API: {e}")
        return "Error: Could not get analysis from AI."


def analyze_commit_list_with_ai(commit_messages: list[str]) -> str:
    """
        sends a list of commit messages to gemini API to anaylze it
    """
    # The prompt remains the same, telling the AI its role and task.
    if not commit_messages :
        raise ValueError("commit messages must be entered")
    
    formatted_commits = "\n".join(f"- {msg.split('/')[-1].strip()}" for msg in commit_messages)
    prompt = f"""
        You are a helpful and encouraging senior software engineer who is an expert in version control best practices.
        Your goal is to review a list of a developer's recent commit messages and provide feedback that is clear, constructive, and educational.
        You should analyze the commits as a whole to identify patterns and habits.
        Your tone should be supportive, aiming to help the developer grow.
        Recognize that this is a list of separate commits, not one single message.
        Based on this list, provide a summary of the developer's habits, structured exactly as follows:

        **Strengths:**
        - (A bullet point listing a specific strength, e.g., "Good use of conventional commit types like 'feat' and 'fix'.")
        - (Another bullet point for a strength.)

        **Weaknesses:**
        - (A bullet point listing a specific weakness, e.g., "Some commit subjects are too vague, like 'docs'.")
        - (Another bullet point for a weakness.)

        **Advice:**
        - (A bullet point with actionable advice directly related to a 'Con'. For example, "For 'docs' commits, specify what was documented, like 'docs: Add setup instructions to README'.")
        - (Another piece of advice.)

        Keep the entire review concise and under 20 lines.

        Here are the commits to analyze:
        {formatted_commits}
    """

    ai_response = generate_ai_response(prompt=prompt)
    
    return ai_response


def commit_best_practice(commit_message:str) -> str :
    """
        Send a commit message to gemini API to rewrite the commit message with the git best practices
    """
    
    if not commit_message :
        raise ValueError("commit message must be entered")
    
    prompt = f"""

        You are a Git expert specializing in writing perfect commit messages.
        Your task is to take a user's commit message and rewrite it to be an ideal example of a conventional commit.
        You must infer the correct type (e.g., feat, fix, docs, style, refactor, test, chore).
        The subject must be clear, concise, and written in the imperative mood (e.g., "Add feature" not "Added feature").
        Provide ONLY the rewritten, ideal commit message and absolutely no extra explanation or text.
        Here is the commit message to rewrite : 

        {commit_message}

    """
    
    ai_response = generate_ai_response(prompt=prompt)
    
    return ai_response
    
    
def write_commit_message(message:str) -> str :
    """
        base on user changes from the message sends the message to gemini API to write the commit base on the commit best practices
    """
    
    if not message :
        raise ValueError("message must be entered")
    
    prompt = f"""
        You are an expert programmer who writes concise, conventional Git commit messages.
        Your task is to take a user's description of their changes and convert it into a perfectly formatted commit message.

        Follow these rules strictly:
        1.  The output must follow the Conventional Commits specification.
        2.  Infer the correct type (`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`) from the description.
        3.  The subject line must be in the imperative mood (e.g., "Add feature," not "Added feature") and start with a lowercase letter.
        4.  If the description is detailed, add a blank line after the subject and write a brief body explaining the 'what' and 'why' in bullet points.
        5.  Your response must contain ONLY the formatted commit message and nothing else. Do not add any extra text like "Here is the commit message:".
        Here is the message :
        
        {message}    
    
    """
    
    response = generate_ai_response(prompt=prompt)
    
    return response


def write_commit_base_on_diff(old_code:str , new_code:str) :
    """Write commit message base on the changes of old and new code"""
    
    if not old_code and not new_code :
        raise ValueError("Old/New codes must be entered")

    prompt = f"""
    You are an expert programmer and a master of writing concise, conventional Git commit messages.
    Your task is to analyze the provided code changes (the 'old code' and the 'new code') and generate a perfectly formatted commit message that summarizes the changes.

    Follow these rules strictly:
    1.  The output must strictly follow the Conventional Commits specification.
    2.  Analyze the code diff to infer the correct commit type: `feat` (a new feature), `fix` (a bug fix), `docs` (documentation only changes), `style` (changes that do not affect the meaning of the code - white-space, formatting, etc.), `refactor` (a code change that neither fixes a bug nor adds a feature), `test` (adding missing tests or correcting existing tests), or `chore` (changes to the build process or auxiliary tools).
    3.  The subject line must be in the imperative mood (e.g., "refactor user authentication," not "refactored user authentication").
    4.  The subject line must not be capitalized and should be concise (ideally under 50 characters).
    5.  If the changes are non-trivial, add a blank line after the subject and write a brief body explaining the 'what' and 'why' of the changes. Use bullet points for clarity.
    6.  Crucially, your response must contain ONLY the formatted commit message and nothing else. Do not include any introductory text, explanations, or apologies.

    ---
    Here is the old code:
    ```
    {old_code}
    ```

    ---
    Here is the new code:
    ```
    {new_code}
    ```
    ---
    """
    
    response = generate_ai_response(prompt=prompt)
    
    return response


def write_commits_for_staged_changes(staged_changes:list[dict]) -> str :
    """Write commit message for user's staged changes"""
    
    if not staged_changes :
        raise ValueError("Staged changes must be enetered")
    
    prompt = f"""You are an expert software developer and an expert at writing concise, high-quality Git commit messages. Your task is to analyze a set of code changes and generate a commit message that follows the Conventional Commits specification.

    ## CONTEXT
    The provided data contains all the file changes for the commit. The data is a JSON object where each key is a file path and the value is a list containing two strings: the content of the file BEFORE the change, and the content AFTER the change.

    - If a file was newly created, its "before" content will be an empty string.
    - If a file was deleted, its "after" content will be an empty string.

    ## TASK
    1.  **Analyze the Diff:** Carefully examine the differences between the "before" and "after" content for all provided files to understand the overall purpose of the changes.
    2.  **Determine Intent:** Do not just list the changes. Your primary goal is to understand the *reason* for the change. Was it a new feature, a bug fix, a performance improvement, a code refactor, or documentation?
    3.  **Generate Commit Message:** Write a single, holistic commit message that summarizes the entire set of changes.

    ## OUTPUT FORMAT
    The message MUST strictly follow the Conventional Commits specification.

    - **Format:** `<type>[optional scope]: <subject>`
    - The subject line must be 50 characters or less.
    - `<type>` must be one of: `feat`, `fix`, `refactor`, `chore`, `docs`, `style`, `test`, `perf`.
    - **Body (Optional):** If needed, provide a more detailed explanation of the changes after a single blank line. Explain the "why" behind the change, not the "how".
    - **Footer (Optional):** Use for breaking changes (`BREAKING CHANGE: ...`) or referencing issue numbers.

    ## CODE CHANGES
    ```json
    {staged_changes}
    """
    
    result = generate_ai_response(prompt=prompt)
    
    return result