import requests
import json
import markdown
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus

# Setup directories
os.makedirs("scrapedIcons", exist_ok=True)

# 1. Load Files
myApps = json.load(open("resources/my-apps.json"))
scraping = json.load(open("resources/scraping.json"))
readMeTemplate = open("resources/README_template.txt").read()

myAppTable = ""
scrapedAppTable = ""

# Process existing 'My Apps'
for app in myApps["apps"]:
    github_link = f"https://github.com/{app.get('github', '')}" if app.get('github') else "#"
    myAppTable += f"|<img src=\"{app['iconURL']}\" alt=\"{app['name']}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{app['name']}]({github_link})|{app['versions'][0]['version']}|\n"

# 2. Main Loop
for repo_info in scraping:
    name = repo_info["name"]
    bundleID = repo_info["bundleID"]
    versions = []
    
    # Defaults from JSON
    author = repo_info.get("author", "Unknown")
    subtitle = repo_info.get("description", "No description provided.")
    localizedDescription = repo_info.get("description", "No description provided.")

    print(f"Processing: {name}...")

    # CASE A: DIRECT LINK (Manual Entry)
    if "directURL" in repo_info:
        versions.append({
            "version": repo_info.get("version", "1.0"),
            "date": "2026-01-01T00:00:00Z",
            "localizedDescription": localizedDescription,
            "downloadURL": repo_info["directURL"],
            "size": 0
        })
        link = repo_info["directURL"]

    # CASE B: GITHUB SCRAPING
    elif "github" in repo_info:
        repo = repo_info["github"]
        link = f"https://github.com/{repo}"
        try:
            data = requests.get(f"https://api.github.com/repos/{repo}").json()
            author = data.get("owner", {}).get("login", author)
            subtitle = data.get("description", subtitle)
            
            releases = requests.get(f"https://api.github.com/repos/{repo}/releases").json()
            for release in releases:
                asset = next((a for a in release.get("assets", []) if a["name"].endswith(".ipa")), None)
                if asset:
                    versions.append({
                        "version": release["tag_name"].lstrip("v"),
                        "date": release["published_at"],
                        "localizedDescription": BeautifulSoup(markdown.markdown(release.get("body", "")), 'html.parser').get_text(),
                        "downloadURL": asset["browser_download_url"],
                        "size": asset["size"]
                    })
        except Exception as e:
            print(f"Error scraping GitHub for {name}: {e}")

    # CASE C: GITLAB SCRAPING
    elif "gitlab" in repo_info:
        # (GitLab logic remains the same as previous version)
        link = repo_info["gitlab"]
        # ... [GitLab scraping logic here] ...

    if not versions:
        continue

    # 3. Icon Handling
    icon_path = f"scrapedIcons/{bundleID}.png"
    if "iconURL" in repo_info:
        try:
            icon_data = requests.get(repo_info["iconURL"]).content
            with open(icon_path, "wb") as f:
                f.write(icon_data)
            iconURL = f"https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/{icon_path}"
        except:
            iconURL = "https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/scrapedIcons/empty.png"
    else:
        iconURL = "https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/scrapedIcons/empty.png"

    # 4. Build Final Object
    app_entry = {
        "name": name,
        "bundleIdentifier": bundleID,
        "developerName": author,
        "subtitle": subtitle,
        "localizedDescription": localizedDescription,
        "iconURL": iconURL,
        "versions": versions
    }
    myApps["apps"].append(app_entry)
    scrapedAppTable += f"|<img src=\"{iconURL}\" alt=\"{name}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{name}]({link})|{versions[0]['version']}|\n"

# 5. Save Output
readMe = readMeTemplate.replace("# MY APPS TABLE", myAppTable).replace("# AUTO SCRAPED TABLE", scrapedAppTable)

with open("altstore-repo.json", "w") as f:
    json.dump(myApps, f, indent=4)

with open("README.md", "w") as f:
    f.write(readMe)

print("Done! Updated altstore-repo.json and README.md")
