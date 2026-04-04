import requests
import json
import markdown
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus

# Pollinations.ai API key
POLLINATIONS_API_KEY = "pk_GUOSx4tlurUvXLS7"

# Ensure directory exists
os.makedirs("scrapedIcons", exist_ok=True)

# 1. Load Data
try:
    myApps = json.load(open("resources/my-apps.json"))
    scraping = json.load(open("resources/scraping.json"))
    readMeTemplate = open("resources/README_template.txt").read()
except FileNotFoundError as e:
    print(f"Error: Missing required file: {e}")
    exit(1)

myAppTable = ""
scrapedAppTable = ""

# Helper: Generate description and tint color via Pollinations.ai
def generate_with_ai(app_name, readme_content):
    prompt = f"Given this iOS app '{app_name}' with README:\n\n{readme_content[:500]}\n\nRespond ONLY with JSON (no markdown): {{'description': 'short 1-2 sentence description', 'tintColor': 'hex color like #FF5733'}}"
    
    try:
        res = requests.post(
            "https://api.pollinations.ai/v1/chat/completions",
            json={
                "model": "nova-fast",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200
            },
            headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"},
            timeout=15
        )
        if res.status_code == 200:
            data = res.json()
            content = data["choices"][0]["message"]["content"].strip()
            # Remove markdown code blocks if present
            content = content.replace("```json", "").replace("```", "").strip()
            result = json.loads(content)
            return result.get("description", "No description"), result.get("tintColor", "#007AFF")
    except Exception as e:
        print(f"AI generation failed: {e}")
    
    return None, "#007AFF"

# Process 'My Apps' (Manual/Static list)
for app in myApps.get("apps", []):
    gh = app.get('github', '')
    link = f"https://github.com/{gh}" if gh else "#"
    myAppTable += f"|<img src=\"{app['iconURL']}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{app['name']}]({link})|{app['versions'][0]['version']}|\n"

# Helper: Fetch README from GitHub
def fetch_github_readme(repo):
    try:
        readme_url = f"https://raw.githubusercontent.com/{repo}/main/README.md"
        res = requests.get(readme_url, timeout=10)
        if res.status_code == 200:
            return res.text
        readme_url = f"https://raw.githubusercontent.com/{repo}/master/README.md"
        res = requests.get(readme_url, timeout=10)
        if res.status_code == 200:
            return res.text
    except:
        pass
    return None

# Helper: Fetch README from GitLab
def fetch_gitlab_readme(host, path):
    try:
        path_encoded = quote_plus(path.lstrip('/'))
        readme_url = f"https://{host}/api/v4/projects/{path_encoded}/repository/files/README.md/raw?ref=main"
        res = requests.get(readme_url, timeout=10)
        if res.status_code == 200:
            return res.text
        readme_url = f"https://{host}/api/v4/projects/{path_encoded}/repository/files/README.md/raw?ref=master"
        res = requests.get(readme_url, timeout=10)
        if res.status_code == 200:
            return res.text
    except:
        pass
    return None

# 2. Main Scraping Loop
for repo_info in scraping:
    name = repo_info["name"]
    bundleID = repo_info["bundleID"]
    versions = []
    
    # Metadata Defaults
    author = repo_info.get("author", "Unknown")
    subtitle = repo_info.get("description", "No description.")
    description = repo_info.get("description", "No description.")
    tintColor = repo_info.get("tintColor", "#007AFF")
    link = "#"

    print(f"Processing: {name}")

    # OPTION A: DIRECT LINK (High Priority)
    if "directURL" in repo_info:
        link = repo_info["directURL"]
        versions.append({
            "version": repo_info.get("version", "1.0"),
            "date": "2026-04-04T00:00:00Z",
            "localizedDescription": description,
            "downloadURL": repo_info["directURL"],
            "size": 0
        })

    # OPTION B: GITHUB
    elif "github" in repo_info:
        repo = repo_info["github"]
        link = f"https://github.com/{repo}"
        api_url = f"https://api.github.com/repos/{repo}"
        
        try:
            repo_data = requests.get(api_url).json()
            author = repo_data.get("owner", {}).get("login", author)
            subtitle = repo_data.get("description", subtitle)
            
            # Fetch full README
            readme_content = fetch_github_readme(repo)
            if readme_content:
                # Generate AI description and tint color
                ai_desc, ai_color = generate_with_ai(name, readme_content)
                if ai_desc:
                    description = ai_desc
                    tintColor = ai_color
                else:
                    # Fallback to markdown parsing
                    description = BeautifulSoup(markdown.markdown(readme_content), 'html.parser').get_text().strip()
            
            rel_api = f"{api_url}/releases"
            releases = requests.get(rel_api).json()
            
            for rel in releases:
                asset = next((a for a in rel.get("assets", []) if a["name"].endswith(".ipa")), None)
                if asset:
                    versions.append({
                        "version": rel["tag_name"].lstrip("v"),
                        "date": rel["published_at"],
                        "localizedDescription": BeautifulSoup(markdown.markdown(rel.get("body", "")), 'html.parser').get_text(),
                        "downloadURL": asset["browser_download_url"],
                        "size": asset["size"]
                    })
        except Exception as e:
            print(f"Failed GitHub scrape for {name}: {e}")

    # OPTION C: GITLAB
    elif "gitlab" in repo_info:
        parsed = urlparse(repo_info["gitlab"])
        host = parsed.netloc
        path = parsed.path
        link = repo_info["gitlab"]
        
        try:
            readme_content = fetch_gitlab_readme(host, path)
            if readme_content:
                # Generate AI description and tint color
                ai_desc, ai_color = generate_with_ai(name, readme_content)
                if ai_desc:
                    description = ai_desc
                    tintColor = ai_color
                else:
                    description = BeautifulSoup(markdown.markdown(readme_content), 'html.parser').get_text().strip()
            
            path_encoded = quote_plus(path.lstrip('/'))
            rel_api = f"https://{host}/api/v4/projects/{path_encoded}/releases"
            releases = requests.get(rel_api).json()
            
            for rel in releases:
                asset = next((l["direct_asset_url"] for l in rel.get("assets", {}).get("links", []) if l["name"].endswith(".ipa")), None)
                if asset:
                    versions.append({
                        "version": rel["tag_name"].lstrip("v"),
                        "date": rel["released_at"],
                        "localizedDescription": BeautifulSoup(markdown.markdown(rel.get("description", "")), 'html.parser').get_text(),
                        "downloadURL": asset,
                        "size": 0
                    })
        except Exception as e:
            print(f"Failed GitLab scrape for {name}: {e}")

    if not versions:
        continue

    # 3. Icon Download
    icon_url = repo_info.get("iconURL")
    icon_dest = f"scrapedIcons/{bundleID}.png"
    final_icon = f"https://raw.githubusercontent.com/dsewerek/iOS-Repo/main/scrapedIcons/empty.png"
    
    if icon_url:
        try:
            res = requests.get(icon_url, timeout=10)
            if res.status_code == 200:
                with open(icon_dest, "wb") as f:
                    f.write(res.content)
                final_icon = f"https://raw.githubusercontent.com/dsewerek/iOS-Repo/main/{icon_dest}"
        except Exception as e:
            print(f"Failed to download icon for {name}: {e}")

    # 4. Assemble
    app_entry = {
        "name": name,
        "bundleIdentifier": bundleID,
        "developerName": author,
        "subtitle": subtitle,
        "localizedDescription": description,
        "iconURL": final_icon,
        "tintColor": tintColor,
        "versions": versions
    }
    myApps["apps"].append(app_entry)
    scrapedAppTable += f"|<img src=\"{final_icon}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{name}]({link})|{versions[0]['version']}|\n"

# 5. Save Files
final_readme = readMeTemplate.replace("# MY APPS TABLE", myAppTable).replace("# AUTO SCRAPED TABLE", scrapedAppTable)

with open("altstore-repo.json", "w") as f:
    json.dump(myApps, f, indent=4)

with open("README.md", "w") as f:
    f.write(final_readme)

print("Files updated successfully.")
