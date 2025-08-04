import requests
import logging
import re
# third party
import asyncio
import aiohttp
from decouple import config
from icecream import ic
from typing import Optional , Literal , Iterator , Tuple
from dataclasses import dataclass
# local
from github.urls import (
    GITHUB_COMMIT_URL,
    GITHUB_USER_URL,
    GITHUB_USERS_REPO_URL
)
from github.exceptions import (
    EmptyCommitHistory
)
from github.utils import get_page_number

logger = logging.getLogger(__name__)
    
class GithubProfile:
    
    def _set_owner_name(self , token:str) -> str | None :
        """Set owner name to fetch further data"""
        try :
            response = requests.get(
                url=GITHUB_USER_URL, 
                headers =  {
                    "Authorization" : f"Bearer {token}"
                },
                params = {
                    "type" : "all"
                }
            )
            if response.status_code == 200 :
                data = response.json()
                ic(data)
                owner_name = data.get("login" , None)
                avatar = data.get("avatar_url" , None)
                
                if owner_name is None :
                    raise ValueError("Owner cannot be None , Failed to fetch user's name")
                
                setattr(self , "owner" , owner_name)
                setattr(self , "avatar" , avatar)
                logger.info("User got the owner name successfully")
                return owner_name
            else :
                return None
            
        except Exception as e :
            logger.error(f"{e} happened while getting the owner name")
            raise e
        
                
    def test_github_connection(self, token:str) -> bool :
        """test connection with the user token"""
        try :
            response = requests.get(
                url=GITHUB_USER_URL, 
                headers =  {
                    "Authorization" : f"Bearer {token}"
                },
                params = {
                    "type" : "all"
                }
            )
            if response.status_code == 200 :
                return True
            else :
                return False
            
        except Exception as e :
            raise e
        

    @property
    def get_owner(self) -> str:
        return self.owner

@dataclass
class GithubRepo :
    page : int = 1
    per_page : int = 30
    
    def get_user_repositories(self , token:str , owner:str , page: Optional[int] = None , per_page : Optional[int] = None ) -> Iterator[str]:    
        """Fetch user's repoistory list then pass to another function to set needed attrs"""
        page_number =  page if page is not None else self.page,
        per_page_number = per_page if per_page is not None else self.per_page
        # Avoid getting more than 30 for single page repo
        
        if per_page_number > 30 :
            raise ValueError("Maximum repos to fetch in single page is 30") 
        
        response = requests.get(
            url = GITHUB_USERS_REPO_URL.format(),
            headers ={
            "Authorization" : f"Bearer {token}",
            },
            params =  {
                "page" : page_number,
                "per_page" : per_page_number
            }
        )
        
        repo_list = [
            f"{owner}/{repo.get('name', '').lower()}"
            for repo in response.json()
        ] if response.status_code == 200 else []
        
        logger.info(f"User got the repo list for the {owner} successfully")
        return repo_list

@dataclass
class GithubCommit:
    total_commits : int = 0
    commit_list : list = None 
    page : int = 1
    per_page : int = 10
    next_pages : list = None
    
    def get_repo_commits(self , token:str , owner:str , repo:str , page : Optional[int] = None , per_page : Optional[int] = None) -> Iterator[str] :
        page_number =  page if page is not None else self.page
        per_page_number = per_page if per_page is not None else self.per_page
        try :
            response = requests.get(
                url = GITHUB_COMMIT_URL.format(owner=owner , repo=repo),
                headers = {
                    "Authorization" : f"Bearer {token}"
                },
                params = {
                    "page" : page_number,
                    "per_page" : per_page_number
                }
            )
        except Exception as e:
            logger.error(f"{e} happened while fetching {repo} tokens")
            raise e
        
        if response.status_code == 200 :
            data = response.json()
            # When the status appear in the response there is not commit for the repo    
            if "status" in data :
                raise EmptyCommitHistory

            if self.commit_list is None :
                self.commit_list = []
            
            for commit in data :
                commit_data = commit.get("commit" , None)
                
                # combine the commit data and message to saving it
                if commit_data is not None :
                    commit_message = commit_data.get("message")
                    commit_date = commit_data.get("author" , None).get("date" , None)
                    self.commit_list.append(f"{commit_date}/{commit_message}")
            # get the next pages if they exist
            if page_number == 1 :
                self.next_pages = []
                next_page = response.headers.get("Link" , None)
                self._get_next_pages(next_page , token , owner , repo , per_page_number)
        
            return self.commit_list
            

    def _get_next_pages(self, link: str, token: str, owner: str, repo: str, per_page: int) -> None:
        """
        Fetches all remaining pages of commits based on the Link header
        """
        # parse link headers
        page_info = self._parse_link_header(link)

        if not page_info:
            return

        next_page, last_page = page_info
        # loop through pages to fetch commits
        for page in range(next_page, last_page + 1):
            self.get_repo_commits(token, owner, repo, page, per_page)

    def _parse_link_header(self, link_header: str) -> Optional[Tuple[int, int]]:
        """
        Parses the Link header using regex to find the next and last page numbers
        """
        if not link_header:
            return None

        # Regex to have dict of rel an url
        # TODO double check the regex it was created by AI
        rel_links = {
            rel: url
            for url, rel in re.findall(r'<([^>]+)>;\s*rel="([^"]+)"', link_header)
        }

        next_url = rel_links.get("next")
        last_url = rel_links.get("last")
        # if next and last page don't exists at the same time 
        if not next_url or not last_url:
            return None
        try:
            # get the next , last page number
            next_page_num = get_page_number(next_url)
            last_page_num = get_page_number(last_url)
            return next_page_num, last_page_num
        except (KeyError, ValueError):
            # TODO handle cases where page param is missing or not an integer.
            return None