import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import time
from datetime import datetime
import json
import random
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from pathlib import Path
import csv
from urllib.parse import quote
import aiofiles

console = Console()

class TweetCSVHandler:
    def __init__(self, keyword: str):
        self.keyword = keyword
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = f"tweets_{keyword}_{timestamp}.csv"
        self._count = 0
        
        # CSV 헤더 정의
        self.headers = [
            'id', 'text', 'user_name', 'user_handle', 
            'timestamp', 'collected_at', 'retweet_count',
            'reply_count', 'like_count'
        ]
        
        # CSV 파일 생성 및 헤더 작성
        with open(self.filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
        
        console.print(f"[green]'{keyword}' 데이터를 저장할 {self.filename} 파일이 생성되었습니다.[/green]")

    def write_tweet(self, tweet_data: dict) -> int:
        try:
            processed_data = {
                'id': tweet_data.get('id', ''),
                'text': tweet_data.get('text', ''),
                'user_name': tweet_data.get('user_name', ''),
                'user_handle': tweet_data.get('user_handle', ''),
                'timestamp': tweet_data.get('timestamp', ''),
                'collected_at': tweet_data.get('collected_at', ''),
                'retweet_count': tweet_data.get('stats', {}).get('retweet', '0'),
                'reply_count': tweet_data.get('stats', {}).get('reply', '0'),
                'like_count': tweet_data.get('stats', {}).get('like', '0')
            }
            
            with open(self.filename, 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerow(processed_data)
            
            self._count += 1
            return self._count
            
        except Exception as e:
            console.print(f"[red]데이터 저장 중 오류 발생: {str(e)}[/red]")
            return self._count

    @property
    def count(self):
        return self._count

class XScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.processed_tweet_ids = set()
    
    async def initialize(self):
        """브라우저 초기화"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--start-maximized',
                '--disable-extensions',
            ]
        )
        
        # 단일 컨텍스트 설정
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )
        
        # 자동화 감지 방지
        await self.context.add_init_script("""
            delete Object.getPrototypeOf(navigator).webdriver;
            navigator.permissions.query = async (parameters) => ({state: 'granted'});
        """)
        
        self.page = await self.context.new_page()
    
    async def save_cookies(self, cookie_file='twitter_cookies.json'):
        """쿠키 저장"""
        cookies = await self.context.cookies()
        async with aiofiles.open(cookie_file, 'w') as f:
            await f.write(json.dumps(cookies))
        console.print(f"[green]쿠키가 저장되었습니다.[/green]")
    
    async def load_cookies(self, cookie_file='twitter_cookies.json'):
        """쿠키 불러오기"""
        try:
            async with aiofiles.open(cookie_file, 'r') as f:
                content = await f.read()
            cookies = json.loads(content)
            await self.context.add_cookies(cookies)
            console.print("[green]쿠키를 불러왔습니다.[/green]")
            return True
        except Exception as e:
            console.print(f"[yellow]쿠키 로드 실패: {str(e)}[/yellow]")
            return False
    
    async def manual_login(self):
        """수동 로그인"""
        console.print("[bold cyan]수동 로그인 절차 시작[/bold cyan]")
        console.print("1. 브라우저에서 X에 로그인해주세요.")
        console.print("2. 로그인이 완료되면 Enter를 눌러주세요.")
        
        await self.page.goto('https://twitter.com/i/flow/login')
        input("로그인이 완료되면 Enter를 눌러주세요...")
        
        if await self.check_login():
            console.print("[green]로그인 성공! 쿠키를 저장합니다.[/green]")
            await self.save_cookies()
            return True
        return False
    
    async def check_login(self):
        """로그인 상태 확인"""
        try:
            await self.page.goto('https://twitter.com/home')
            await asyncio.sleep(2)
            return 'login' not in self.page.url
        except Exception:
            return False
    
    async def search_tweets(self, query: str):
        """트윗 검색 및 수집"""
        csv_handler = TweetCSVHandler(query)
        
        try:
            # 직접 검색 페이지로 이동
            encoded_query = quote(query)
            search_url = f'https://twitter.com/search?q={encoded_query}&f=live'
            await self.page.goto(search_url)
            await asyncio.sleep(3)  # 페이지 로딩 대기
            
            # 검색 결과 확인
            no_result = await self.page.query_selector('div[data-testid="emptyState"]')
            if no_result:
                console.print(f"[yellow]'{query}'에 대한 검색 결과가 없습니다.[/yellow]")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task(f"[cyan]'{query}' 수집 중...", total=None)
                
                last_height = await self.page.evaluate('document.body.scrollHeight')
                no_new_tweets_count = 0
                
                while no_new_tweets_count < 5:
                    # 트윗 요소 찾기
                    tweet_elements = await self.page.query_selector_all('article[data-testid="tweet"]')
                    found_new_tweets = False
                    
                    for tweet in tweet_elements:
                        try:
                            tweet_data = await self._extract_tweet_data(tweet)
                            if tweet_data and tweet_data['id'] not in self.processed_tweet_ids:
                                current_count = csv_handler.write_tweet(tweet_data)
                                self.processed_tweet_ids.add(tweet_data['id'])
                                found_new_tweets = True
                                progress.update(task, description=f"[cyan]'{query}': {current_count}개 수집[/cyan]")
                        except Exception as e:
                            console.print(f"[yellow]트윗 추출 실패: {str(e)}[/yellow]")
                    
                    if not found_new_tweets:
                        no_new_tweets_count += 1
                    else:
                        no_new_tweets_count = 0
                    
                    # 부드러운 스크롤
                    scroll_amount = random.randint(300, 700)
                    steps = random.randint(5, 10)
                    
                    for _ in range(steps):
                        await self.page.evaluate(f'window.scrollBy(0, {scroll_amount/steps})')
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                    
                    # 새로운 컨텐츠 확인
                    new_height = await self.page.evaluate('document.body.scrollHeight')
                    if new_height == last_height:
                        no_new_tweets_count += 1
                        
                        # 페이지 새로고침
                        if no_new_tweets_count == 3:
                            await self.page.reload()
                            await asyncio.sleep(3)
                            no_new_tweets_count = 0
                    
                    last_height = new_height
                    await asyncio.sleep(random.uniform(1, 2))
            
            console.print(f"[green]'{query}'에 대해 총 {csv_handler.count}개의 트윗을 수집했습니다.[/green]")
            
        except Exception as e:
            console.print(f"[red]'{query}' 수집 중 에러: {str(e)}[/red]")
    
    async def _extract_tweet_data(self, tweet_element):
        """트윗 데이터 추출"""
        try:
            # 트윗 ID 추출
            link = await tweet_element.query_selector('a[href*="/status/"]')
            tweet_id = (await link.get_attribute('href')).split('/status/')[-1] if link else None
            
            if not tweet_id or tweet_id in self.processed_tweet_ids:
                return None
            
            # 텍스트 내용
            text = await tweet_element.query_selector('[data-testid="tweetText"]')
            text_content = await text.inner_text() if text else ""
            
            # 시간 정보
            time_element = await tweet_element.query_selector('time')
            timestamp = await time_element.get_attribute('datetime') if time_element else None
            
            # 사용자 정보
            user_element = await tweet_element.query_selector('[data-testid="User-Name"]')
            user_info = (await user_element.inner_text()).split('\n') if user_element else []
            user_name = user_info[0] if user_info else ""
            user_handle = user_info[1] if len(user_info) > 1 else ""
            
            # 통계 정보 수집
            stats = {}
            for stat_type in ['reply', 'retweet', 'like']:
                stat_element = await tweet_element.query_selector(f'[data-testid="{stat_type}"]')
                if stat_element:
                    stats[stat_type] = (await stat_element.inner_text()) or "0"
            
            return {
                'id': tweet_id,
                'text': text_content,
                'user_name': user_name,
                'user_handle': user_handle,
                'timestamp': timestamp,
                'stats': stats,
                'collected_at': datetime.now().isoformat()
            }
        except Exception:
            return None
    
    async def close(self):
        """브라우저 종료"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

async def main():
    scraper = XScraper()
    console.print("[bold cyan]X 스크래퍼 시작[/bold cyan]")
    
    try:
        # 초기화
        await scraper.initialize()
        
        # 쿠키 로드 또는 수동 로그인
        if not await scraper.load_cookies():
            if not await scraper.manual_login():
                console.print("[red]로그인에 실패했습니다.[/red]")
                return
        
        # 검색어 입력
        console.print("\n[bold cyan]검색어들을 입력하세요 (쉼표로 구분)[/bold cyan]")
        console.print("예시: 바카라, 카지노, 토토")
        keywords_input = input("> ")
        keywords = [keyword.strip() for keyword in keywords_input.split(',') if keyword.strip()]
        
        if not keywords:
            console.print("[red]검색어를 입력해주세요.[/red]")
            return
        
        # 각 검색어에 대해 순차적으로 처리
        for i, keyword in enumerate(keywords, 1):
            console.print(f"\n[bold cyan][{i}/{len(keywords)}] '{keyword}' 검색 시작[/bold cyan]")
            await scraper.search_tweets(keyword)
            
            # 검색어 사이에 잠시 대기
            if i < len(keywords):
                wait_time = random.uniform(3, 5)
                console.print(f"[yellow]다음 검색어로 넘어가기 전 {wait_time:.1f}초 대기 중...[/yellow]")
                await asyncio.sleep(wait_time)
        
        console.print("\n[bold green]모든 검색어 처리 완료![/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자가 프로그램을 중단했습니다.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]에러 발생: {str(e)}[/bold red]")
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())