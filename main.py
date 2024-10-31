import os
import aiohttp
import asyncio
import json
import datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

GITHUB_API_URL = "https://api.github.com"
TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {'Authorization': 'Bearer {}'.format(TOKEN),
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'}

# Function to read the repos from a public repository containing repos.json
async def read_repos_from_config():
    url = "https://raw.githubusercontent.com/trongdth/nervos-active-repos/develop/repos.json"  # Replace with your actual URL
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.read()
            repos_data = json.loads(data)
            return repos_data["repos"]

# Async function to fetch commits for a repository within a date range
async def fetch_commits(session, owner, repo, since, until):
    commits = []
    page = 1
    per_page = 200
    while True:
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/commits"
        params = {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "page": page,
            "per_page": per_page
        }
        async with session.get(url, headers=HEADERS, params=params) as response:
            if response.status != 200:
                print(f"Failed to fetch commits for {repo}, status: {response.status}")
                break
            data = await response.json()
            if not data:
                break
            commits.extend(data)
            page += 1
    return commits

# Async function to fetch commits from all repositories
async def fetch_all_commits(repos, since, until):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for repo in repos:
            owner, repo_name = repo.split("/")
            tasks.append(fetch_commits(session, owner, repo_name, since, until))
        results = await asyncio.gather(*tasks)
        return results

# Main function to coordinate fetching all data and generating the report
async def main():
    repos = await read_repos_from_config()  # Read repos from public repos.json
    
    # Define date ranges for current and previous months
    today = datetime.datetime.now()
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - datetime.timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)
    
    # Fetch commits for current month
    commits_current_month = await fetch_all_commits(repos, first_day_current_month, today)
    # Fetch commits for previous month
    commits_previous_month = await fetch_all_commits(repos, first_day_previous_month, first_day_current_month - datetime.timedelta(seconds=1))
    
    # Process commits to get unique developers
    current_developers = get_unique_developers(commits_current_month)
    previous_developers = get_unique_developers(commits_previous_month)
    
    # Calculate metrics
    current_dev_count = len(current_developers)
    previous_dev_count = len(previous_developers)
    
    if previous_dev_count > 0:
        percentage_change = ((current_dev_count - previous_dev_count) / previous_dev_count) * 100
    else:
        percentage_change = 0  # Avoid division by zero
    
    # Identify new developers
    new_developers = current_developers - previous_developers
    new_dev_count = len(new_developers)

    # Calculate total number of commits in the current month
    total_commits_current_month = sum(len(commits) for commits in commits_current_month)
    
    # Generate report
    report = {
        "current_number_of_developers": current_dev_count,
        "percentage_change": percentage_change,
        "number_of_new_developers": new_dev_count,
        "total_commits": total_commits_current_month
    }
    
    # Export report to CSV
    export_report(report, today.month, today.year)
    
    print("Report generated successfully.")

# Helper function to extract unique developers from commit data
def get_unique_developers(commits_list):
    developers = set()
    for commits in commits_list:
        for commit in commits:
            author = commit.get('author')
            if author and author.get('login'):
                developers.add(author['login'])
            else:
                # Handle commits without a GitHub user (e.g., email-only commits)
                commit_author = commit['commit']['author']
                if commit_author and commit_author.get('email'):
                    developers.add(commit_author['email'])
    return developers

# Function to export the report to CSV
def export_report(report, month, year):
    df = pd.DataFrame([report])
    df.to_csv('report/developer_activity_report_{}{}.csv'.format(month, year), index=False)

# Run the main function in asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())
