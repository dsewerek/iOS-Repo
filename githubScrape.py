import requests
import json
import markdown
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus

# Ensure icon directory exists
os.makedirs("scrapedIcons", exist_ok=True)

# 1. Load configuration and templates
myApps = json.load(open("resources/my-apps.json"))
scraping = json.load(open("resources/scraping.json"))
readMe = open("resources/README_template.txt").read()

# Track apps for the README table
myAppTable = ""
scrapedAppTable = ""

# Process existing 'My Apps' from JSON
for app in myApps["apps"]:
    myAppTable += f"|<img src=\"{app['iconURL']}\" alt=\"{app['name']}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{app['name']}](https://github.com/{app.get('github', '')})|{app['versions'][0]['version']}|\n"

# 2. Main Processing Loop
for repo_info in scraping:
    name = repo_info["name"]
    bundleID = repo_info["bundleID"]
    versions = []
    author = repo_info.get("author", "Unknown")
    subtitle = repo_info.get("subtitle", "No description available.")
    localizedDescription = repo_info.get("description", "No detailed description.")

    print(f"Processing {name}...")

    # --- CATEGORY A: GITHUB SCRAPING ---
    if "github" in repo_info:
        repo = repo_info["github"]
        data = requests.get(f"https://api.github.com/repos/{repo}").json()
        
        # Metadata
        author = data.get("owner", {}).get("login", "Unknown")
        subtitle = data.get("description", subtitle)
        
        # Scrape Releases
        releases = requests.get(f"https://api.github.com/repos/{repo}/releases").json()
        for release in releases:
            downloadURL = next((a["browser_download_url"] for a in release.get("assets", []) if a["name"].endswith(".ipa")), None)
            if not downloadURL: continue
            
            versions.append({
                "version": release["tag_name"].lstrip("v"),
                "date": release["published_at"],
                "localizedDescription": BeautifulSoup(markdown.markdown(release.get("body", "")), 'html.parser').get_text(),
                "downloadURL": downloadURL,
                "size": next((a["size"] for a in release["assets"] if a["browser_download_url"] == downloadURL), 0)
            })

    # --- CATEGORY B: GITLAB SCRAPING ---
    elif "gitlab" in repo_info:
        host = urlparse(repo_info["gitlab"]).netloc
        path = urlparse(repo_info["gitlab"]).path
        project_id = quote_plus(path.lstrip('/'))
        data = requests.get(f"https://{host}/api/v4/projects/{project_id}").json()
        
        subtitle = data.get("description", subtitle)
        releases = requests.get(f"https://{host}/api/v4/projects/{project_id}/releases").json()
        
        for release in releases:
            downloadURL = next((a["direct_asset_url"] for a in release.get("assets", {}).get("links", []) if a["name"].endswith(".ipa")), None)
            if not downloadURL: continue
            
            versions.append({
                "version": release["tag_name"].lstrip("v"),
                "date": release["released_at"],
                "localizedDescription": BeautifulSoup(markdown.markdown(release.get("description", "")), 'html.parser').get_text(),
                "downloadURL": downloadURL,
                "size": 0
            })

    # --- CATEGORY C: DIRECT LINK (CUSTOM) ---
    elif "directURL" in repo_info:
        versions.append({
            "version": repo_info.get("version", "1.0"),
            "date": "2024-01-01T00:00:00Z", # Placeholder date
            "localizedDescription": localizedDescription,
            "downloadURL": repo_info["directURL"],
            "size": 0
        })

    if not versions:
        print(f"Skipping {name}: No IPA found.")
        continue

    # --- ICON HANDLING ---
    if "iconURL" in repo_info:
        try:
            icon_data = requests.get(repo_info["iconURL"]).content
            with open(f"scrapedIcons/{bundleID}.png", "wb") as f:
                f.write(icon_data)
            iconURL = f"https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/scrapedIcons/{bundleID}.png"
        except:
            iconURL = "https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/scrapedIcons/empty.png"
    else:
        iconURL = "https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/main/scrapedIcons/empty.png"

    # --- ADD TO REPO OBJECT ---
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

    # --- ADD TO README TABLE ---
    link = repo_info.get("github", repo_info.get("gitlab", repo_info.get("directURL")))
    scrapedAppTable += f"|<img src=\"{iconURL}\" alt=\"{name}\" width=\"100\" height=\"100\" style=\"border-radius: 20px\">|[{name}]({link})|{versions[0]['version']}|\n"

# 3. Finalize Files
readMe = readMe.replace("# MY APPS TABLE", myAppTable)
readMe = readMe.replace("# AUTO SCRAPED TABLE", scrapedAppTable)

print("Saving altstore-repo.json...")
with open("altstore-repo.json", "w") as f:
    json.dump(myApps, f, indent=4)

print("Saving README.md...")
with open("README.md", "w") as f:
    f.write(readMe)
