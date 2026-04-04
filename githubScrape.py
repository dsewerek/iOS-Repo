import requests
import json
import markdown
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus

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

# Process 'My Apps' (Manual/Static list)
for app in myApps.get("apps", []):
    gh = app.get('github', '')
    link = f"https://github.com/{gh}" if gh else "#"
    myAppTable += f"|<img src=\"{app['iconURL']}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{app['name']}]({link})|{app['versions'][0]['version']}|\n"

# 2. Main Scraping Loop
for repo_info in scraping:
    name = repo_info["name"]
    bundleID = repo_info["bundleID"]
    versions = []
    
    # Metadata Defaults
    author = repo_info.get("author", "Unknown")
    subtitle = repo_info.get("description", "No description.")
    description = repo_info.get("description", "No description.")
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
            
            rel_api = f"{api_url}/releases"
            releases = requests.get(rel_api).json()
            
            for rel in releases:
                # Find the first .ipa asset
                asset = next((a for a in rel.get("assets", []) if a["name"].endswith(".ipa")), None)
                if asset:
                    versions.append({
                        "version": rel["tag_name"].lstrip("v"),
                        "date": rel["published_at"],
                        "localizedDescription": BeautifulSoup(markdown.markdown(rel.get("body", "")), 'html.parser').get_text(),
                        "downloadURL": asset["browser_download_url"],
                        "size": asset["size"]
                    })
        except: print(f"Failed GitHub scrape for {name}")

    # OPTION C: GITLAB
    elif "gitlab" in repo_info:
        # Example: https://gitlab.com/user/repo
        parsed = urlparse(repo_info["gitlab"])
        host = parsed.netloc
        path = quote_plus(parsed.path.lstrip('/'))
        link = repo_info["gitlab"]
        
        try:
            rel_api = f"https://{host}/api/v4/projects/{path}/releases"
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
        except: print(f"Failed GitLab scrape for {name}")

    if not versions:
        continue

    # 3. Icon Download
    icon_url = repo_info.get("iconURL")
    icon_dest = f"scrapedIcons/{bundleID}.png"
    final_icon = f"https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/scrapedIcons/empty.png"
    
    if icon_url:
        try:
            res = requests.get(icon_url, timeout=10)
            if res.status_code == 200:
                with open(icon_dest, "wb") as f:
                    f.write(res.content)
                final_icon = f"https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/{icon_dest}"
        except: pass

    # 4. Assemble
    app_entry = {
        "name": name,
        "bundleIdentifier": bundleID,
        "developerName": author,
        "subtitle": subtitle,
        "localizedDescription": description,
        "iconURL": final_icon,
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
