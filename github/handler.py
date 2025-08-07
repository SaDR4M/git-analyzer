import requests
import logging
import re
import os
from pathlib import Path
from typing import Tuple
# third party
import asyncio
import aiohttp
from decouple import config
from icecream import ic
from typing import Optional , Literal , Iterator , Tuple
from dataclasses import dataclass
from git import Repo , InvalidGitRepositoryError
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
        ic(response.json())
        repo_list = []
        for repo in response.json() :
            if response.status_code == 200 :
                repo_list.append(
                    {f"{owner}/{repo.get('name', '').lower()}" : f"{repo.get('clone_url')}"}
                )
        ic(repo_list)
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
        
@dataclass
class GitRepo:
    _repo : Repo = None
    staged_files : list = None
    staged_files_repo : list = None
    file_blobs : list[dict] = None
        
    def _repo(self , path:str) -> list:
        """
        Clone repo to local if path exists we pass it to another function
        to create a instance from local 
        """
        # create path for clone if it does not exists
        if not path :
            raise ValueError("Path must be valid")
        
        directory_exists = self._directory_exist(path)
        if directory_exists :
            
            try :
                repo = Repo(path)
                self._repo = repo
            except InvalidGitRepositoryError :
                return "Selected repo isn't valid"
            
            self._get_stage_changes(repo)
        else :           
            return "Invalid directory path"
        
        # get the staged and unstaged files data
        return self._get_stage_files(repo) , self._get_unstaged_files(repo)

        
    def _directory_exist(self , path:str) -> bool:
        """Check that path exists or not"""

        path_exists = os.path.exists(path=path)

        if not path_exists :
            return False
        return True
            
    def _get_stage_files(self , repo:Repo) -> list :
        """get the file name of staged changes with the change type"""
        # staged diff
        staged_changes = repo.index.diff(repo.head.commit)
        
        files = []
        # get the file name and change type of the file
        for diff in staged_changes :
            ic(diff.a_blob)
            files.append(
                {
                "file_name" : diff.a_path,
                "change_type" : diff.change_type
                }
            )
        self._stage_files = files
        return files
    
    def _get_stage_changes(self , repo:Repo) -> list[Repo]:
        """Get the stage changes to write commit base on them"""
    
        # get staged changes diff
        staged_changes = repo.index.diff(repo.head.commit)
        
        # add the diff objects to a list to reuse it later
        stage_files = []
        for diff in staged_changes:
            stage_files.append(diff)

        self._staged_files_repo = stage_files

    def _get_unstaged_files(self , repo:Repo) -> list | None:
        """Get unstaged files list"""
        # get unstaged files
        untracked_changes = repo.index.diff(None)
        
        if untracked_files :
            untracked_files = [file.a_path for file in untracked_changes]
        else :
            return None

        return untracked_files
    
    def _add_to_stage(self , repo:Repo , file_name:str ) -> None:
        """Add file to staged changes"""
        
        if not file_name :
            raise ValueError("File name is not valid")
        
        repo.index.add(file_name)
        
    
    def _add_all_to_stage(self , repo:Repo) -> None :
        """Stage all files"""
        
        repo.index.add(all=True)
        
    def _remove_from_stage(self , repo:Repo , file_name:str) -> None :
        """Remove the file from staged changes"""
                
        if not file_name :
            raise ValueError("File name is not valid")
        
        repo.index.remove(file_name)
    
    def _remove_all_from_stage(self , repo:Repo) -> None :
        """Remove all messages from staged changes"""
        
        if not repo :
            raise ValueError("Repo must be entered")
        
        repo.index.remove(all=True)
    
    
    def decode_blob(self , diff:object) -> Tuple[str , str] :
        """Decode a & b blobs to strings"""    
        if diff.a_blob and not diff.b_blob :
            raise ValueError("a_blob or b_blob must have value")
        
        # for deleted files the b_blob will be None
        decoded_b_blob = diff.b_blob.data_stream.read().decode('utf-8') if diff.b_blob else "Deleted"            
        
        # for new files the a_blob will be None
        decoded_a_blob = diff.a_blob.data_stream.read().decode('utf-8') if diff.a_blob else "New added"
        
        return decoded_a_blob , decoded_b_blob
    

    def _combine_all_blobs(self) -> list[dict] :
        """Combine all diffs to analyze the staged changes commits"""
        
        combined_diffs = []
        for diff in self._staged_files_repo :
            # for new files a_path will be None
            # we set file path to b_path it's more reliable to do
            file_path = diff.b_path or diff.a_path
            if not file_path :
                raise ValueError("File path cannot be empty")
            
            old_content , new_content = self.decode_blob(diff)
            # combine it
            combined_diffs[file_path] = [old_content , new_content]
            
        return combined_diffs
    
    def _commit(self , message:str) -> bool :
        """Commit generated commit message by AI for staged changes"""
        
        if not message :
            return False
        
        self._repo.index.commit(message)
        
        return True