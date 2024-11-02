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
from typing import List, Dict, Set
import aiofiles
import csv
import os
from urllib.parse import quote
import random
import csv
from datetime import datetime
from rich.console import Console
console = Console()

class csv_handler:
    """실시간 CSV 파일 처리를 위한 클래스"""
    def __init__(self, keyword: str):
        self.keyword = keyword
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.filename = f"tweets_{keyword}_{timestamp}.csv"
        self.count = 0
        
        # CSV 파일 초기화 및 헤더 작성
        self.headers = [
            'id', 'text', 'user_name', 'user_handle', 
            'timestamp', 'collected_at', 'retweet_count',
            'reply_count', 'like_count'
        ]
        
        # 파일 생성 및 헤더 작성
        with open(self.filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
        
        console.print(f"[green]'{keyword}' 데이터를 저장할 {self.filename} 파일이 생성되었습니다.[/green]")
    
    def write_tweet(self, tweet_data: dict) -> int:
        """트윗 데이터를 CSV 파일에 추가하고 현재까지의 트윗 수를 반환"""
        try:
            # stats 딕셔너리를 풀어서 개별 컬럼으로 저장
            processed_data = {
                'id': tweet_data.get('id', ''),
                'text': tweet_data.get('text', ''),
                'user_name': tweet_data.get('user_name', ''),
                'user_handle': tweet_data.get('user_handle', ''),
                'timestamp': tweet_data.get('timestamp', ''),
                'collected_at': tweet_data.get('collected_at', ''),
                'retweet_count': tweet_data.get('stats', {}).get('retweet_count', '0'),
                'reply_count': tweet_data.get('stats', {}).get('reply_count', '0'),
                'like_count': tweet_data.get('stats', {}).get('like_count', '0')
            }
            
            # CSV 파일에 데이터 추가
            with open(self.filename, 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerow(processed_data)
            
            self.count += 1
            return self.count
            
        except Exception as e:
            console.print(f"[red]데이터 저장 중 오류 발생: {str(e)}[/red]")
            return self.count
    
    def get_count(self) -> int:
        """현재까지 수집된 트윗 수 반환"""
        return self.count

class CSVHandler:
    """실시간 CSV 파일 처리를 위한 클래스"""
    def __init__(self, keyword: str):
        self.keyword = keyword
        self.filename = f"tweets_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.count = 0
        
        # CSV 파일 초기화
        self.headers = ['id', 'text', 'user_name', 'user_handle', 'timestamp', 'collected_at']
        with open(self.filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
    
    def write_tweet(self, tweet_data: dict):
        """트윗 데이터를 CSV 파일에 추가"""
        with open(self.filename, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writerow(tweet_data)
        self.count += 1
        return self.count

class XParallelScraper:
    def __init__(self):
        self.processed_tweet_ids: Set[str] = set()
        self.playwright = None
        self.browser = None
        self.contexts = []
        self.csv_handlers = {}
    
    async def initialize(self, max_parallel=3):
        """병렬 처리를 위한 초기화"""
        self.playwright = await async_playwright().start()
        
        # 브라우저 설정 강화
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-blink-features',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-web-security',  # CORS 비활성화
                '--disable-features=TranslateUI',
                '--disable-features=LazyFrameLoading',  # 지연 로딩 비활성화
                '--disable-logging',
                '--no-default-browser-check',
                '--start-maximized',  # 창 최대화
                '--window-size=1920,1080',  # 윈도우 크기 설정
                f'--window-position={random.randint(0,100)},{random.randint(0,100)}',  # 랜덤 위치
                '--disable-extensions'
            ]
        )
        
        # 컨텍스트 설정 강화
        for _ in range(max_parallel):
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                java_script_enabled=True,
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation', 'notifications'],
                color_scheme='dark',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'SEC-CH-UA': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                    'SEC-CH-UA-MOBILE': '?0',
                    'SEC-CH-UA-PLATFORM': '"macOS"'
                }
            )
            
            # 브라우저 지문 숨기기
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        },
                        {
                            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                            1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                            description: "Native Client",
                            filename: "internal-nacl-plugin",
                            length: 2,
                            name: "Native Client"
                        }
                    ]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'MacIntel'
                });
                
                // WebGL 지문 수정
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.'
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine'
                    }
                    return getParameter.apply(this, arguments);
                };
                
                // Chrome 런타임 설정
                window.chrome = {
                    app: {
                        isInstalled: false,
                        InstallState: {
                            DISABLED: 'disabled',
                            INSTALLED: 'installed',
                            NOT_INSTALLED: 'not_installed'
                        },
                        RunningState: {
                            CANNOT_RUN: 'cannot_run',
                            READY_TO_RUN: 'ready_to_run',
                            RUNNING: 'running'
                        }
                    },
                    runtime: {
                        OnInstalledReason: {
                            CHROME_UPDATE: 'chrome_update',
                            INSTALL: 'install',
                            SHARED_MODULE_UPDATE: 'shared_module_update',
                            UPDATE: 'update'
                        },
                        OnRestartRequiredReason: {
                            APP_UPDATE: 'app_update',
                            OS_UPDATE: 'os_update',
                            PERIODIC: 'periodic'
                        },
                        PlatformArch: {
                            ARM: 'arm',
                            ARM64: 'arm64',
                            MIPS: 'mips',
                            MIPS64: 'mips64',
                            X86_32: 'x86-32',
                            X86_64: 'x86-64'
                        },
                        PlatformNaclArch: {
                            ARM: 'arm',
                            MIPS: 'mips',
                            MIPS64: 'mips64',
                            X86_32: 'x86-32',
                            X86_64: 'x86-64'
                        },
                        PlatformOs: {
                            ANDROID: 'android',
                            CROS: 'cros',
                            LINUX: 'linux',
                            MAC: 'mac',
                            OPENBSD: 'openbsd',
                            WIN: 'win'
                        },
                        RequestUpdateCheckStatus: {
                            NO_UPDATE: 'no_update',
                            THROTTLED: 'throttled',
                            UPDATE_AVAILABLE: 'update_available'
                        }
                    }
                };
            """)
            
            self.contexts.append(context)
    
    async def save_cookies(self, context, cookie_file='twitter_cookies.json'):
        """쿠키 저장"""
        cookies = await context.cookies()
        async with aiofiles.open(cookie_file, 'w') as f:
            await f.write(json.dumps(cookies))
        console.print(f"[green]쿠키가 저장되었습니다.[/green]")
    
    async def load_cookies(self, cookie_file='twitter_cookies.json'):
        """저장된 쿠키 불러오기"""
        try:
            async with aiofiles.open(cookie_file, 'r') as f:
                content = await f.read()
            cookies = json.loads(content)
            
            for context in self.contexts:
                await context.add_cookies(cookies)
            console.print("[green]쿠키를 불러왔습니다.[/green]")
            return True
        except Exception as e:
            console.print(f"[yellow]쿠키 로드 실패: {str(e)}[/yellow]")
            return False
    
    async def manual_login(self):
        """수동 로그인"""
        if not self.contexts:
            return False
            
        context = self.contexts[0]
        page = await context.new_page()
        
        console.print("[bold cyan]수동 로그인 절차 시작[/bold cyan]")
        console.print("1. 브라우저에서 X에 로그인해주세요.")
        console.print("2. 로그인 완료 후 Enter를 눌러주세요.")
        
        await page.goto('https://twitter.com/i/flow/login')
        input("로그인이 완료되면 Enter를 눌러주세요...")
        
        if await self.check_login(page):
            console.print("[green]로그인 성공! 쿠키를 저장합니다.[/green]")
            await self.save_cookies(context)
            await page.close()
            return True
        
        await page.close()
        return False
    
    async def check_login(self, page):
        """로그인 상태 확인"""
        try:
            await page.goto('https://twitter.com/home')
            await asyncio.sleep(2)
            return 'login' not in page.url
        except Exception:
            return False
    
    async def search_tweets_parallel(self, keywords: List[str]):
        """병렬 검색 실행"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
        ) as progress:
            # 각 키워드별 태스크 생성
            tasks = {
                keyword: progress.add_task(f"[cyan]'{keyword}' 수집 중...", total=None)
                for keyword in keywords
            }
            
            # 검색 실행
            search_tasks = []
            for i, keyword in enumerate(keywords):
                context = self.contexts[i % len(self.contexts)]
                task = asyncio.create_task(
                    self.search_tweets(
                        keyword, 
                        context, 
                        progress, 
                        tasks[keyword]
                    )
                )
                search_tasks.append(task)
            
            await asyncio.gather(*search_tasks, return_exceptions=True)
    
    async def search_tweets(self, query: str, context, progress, task_id):
        page = await context.new_page()
        
        # 페이지별 추가 설정
        await page.set_extra_http_headers({
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        })
        
        # 쿼리 인코딩
        encoded_query = quote(query)
        search_url = f'https://twitter.com/search?q={encoded_query}&f=live&pf=on'
        
        # 랜덤 지연 추가
        await asyncio.sleep(random.uniform(2, 4))
        
        try:
            await page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            last_height = await page.evaluate('document.body.scrollHeight')
            no_new_tweets_count = 0
            
            while no_new_tweets_count < 5:
                tweet_elements = await page.query_selector_all('article[data-testid="tweet"]')
                
                found_new_tweets = False
                for tweet in tweet_elements:
                    try:
                        tweet_data = await self._extract_tweet_data(tweet)
                        if tweet_data and tweet_data['id'] not in self.processed_tweet_ids:
                            # 즉시 CSV에 기록
                            tweet_count = csv_handler.write_tweet(tweet_data)
                            self.processed_tweet_ids.add(tweet_data['id'])
                            found_new_tweets = True
                            progress.update(task_id, description=f"[cyan]'{query}': {tweet_count}개 수집[/cyan]")
                    except Exception as e:
                        console.print(f"[yellow]트윗 추출 실패: {str(e)}[/yellow]")
                
                if not found_new_tweets:
                    no_new_tweets_count += 1
                else:
                    no_new_tweets_count = 0
                
                # 스크롤
                await self._smooth_scroll(page)
                await asyncio.sleep(random.uniform(1, 2))
                
                # 새로운 컨텐츠 확인
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    no_new_tweets_count += 1
                else:
                    no_new_tweets_count = 0
                last_height = new_height
                
                # 페이지 새로고침
                if no_new_tweets_count == 3:
                    await page.reload()
                    await asyncio.sleep(2)
            
            console.print(f"[green]'{query}'에 대해 총 {csv_handler.count}개의 트윗을 수집했습니다.[/green]")
            
        except Exception as e:
            console.print(f"[red]'{query}' 수집 중 에러: {str(e)}[/red]")
        
        finally:
            await page.close()
    
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
            
            return {
                'id': tweet_id,
                'text': text_content,
                'user_name': user_name,
                'user_handle': user_handle,
                'timestamp': timestamp,
                'collected_at': datetime.now().isoformat()
            }
        except Exception:
            return None
    
    async def _smooth_scroll(self, page, distance=300, steps=10):
        """부드러운 스크롤"""
        for _ in range(steps):
            await page.evaluate(f'window.scrollBy(0, {distance/steps})')
            await asyncio.sleep(0.05)
    
    async def close(self):
        """리소스 정리"""
        for context in self.contexts:
            await context.close()
        await self.browser.close()
        await self.playwright.stop()

async def main():
    # 최대 동시 실행 수 설정
    MAX_PARALLEL = 3
    
    scraper = XParallelScraper()
    console.print("[bold cyan]X 실시간 스크래퍼 시작[/bold cyan]")
    
    try:
        # 초기화
        await scraper.initialize(max_parallel=MAX_PARALLEL)
        
        # 쿠키 로드 또는 수동 로그인
        if not await scraper.load_cookies():
            if not await scraper.manual_login():
                console.print("[red]로그인에 실패했습니다.[/red]")
                return
        
        # 검색어 입력
        console.print("\n[bold cyan]검색어를 입력하세요 (쉼표로 구분)[/bold cyan]")
        console.print(f"최대 {MAX_PARALLEL}개의 검색어가 동시에 처리됩니다.")
        keywords_input = input("> ")
        keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
        
        if not keywords:
            console.print("[red]검색어를 입력해주세요.[/red]")
            return
        
        # 병렬 검색 실행
        await scraper.search_tweets_parallel(keywords)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자가 프로그램을 중단했습니다.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]에러 발생: {str(e)}[/bold red]")
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())