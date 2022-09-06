import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
import re
from bs4 import BeautifulSoup


class Isui:
    def __init__(self, login=None, password=None):
        self.httpAdapter = HTTPAdapter(max_retries=2)
        self.httpSession = requests.Session()
        self.httpSession.mount('https://helpdesk.efko.ru', self.httpAdapter)
        self.httpSession.headers.update({'origin': 'https://helpdesk.efko.ru',
        'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36'})
        self.ssl_check = True
        self.user_id = None
        self.login = login
        self.password = password

    def setAccount(self, login, password):
        self.login = login
        self.password = password

    def _get(self, url, data=None, params=None):
        """Загрузка страници"""
        if params is None:
            params = {}
        if data is None:
            data = {}
        try:
            response = self.httpSession.get(url, data=data, params=params, verify=self.ssl_check)
            response.raise_for_status()
        except HTTPError as http_err:
            print(http_err)
            return 1, None
        except Exception as err:
            print(err)
            return 1, None
        else:
            if 'Время сессии истекло' in response.text:
                res = self.authorization()
                return 3, None
        return 0, response

    def _post(self, url, data = {}, params = {}):
        try:
            response = self.httpSession.post(url,
            data = data, params=params, verify = self.ssl_check)
            response.raise_for_status()
        except HTTPError as http_err:
            print(http_err)
            return 1, None
        except Exception as err:
            print(err)
            return 1, None
        else:
            if 'Сервер не отвечает' in response.text:
                return 1, None
            if 'Неправильный логин или пароль' in response.text:
                return 2, None
        return 0, response

    def authorization(self):
        """Авторизация на сервере ИСУИ"""
        query_data = {'login': self.login}
        query_data.update({'password': self.password})
        query_data.update({'mypage': ''})

        res, response = self._post('https://helpdesk.efko.ru/login.php', data = query_data)
        if res:
            return res
        self.user_id = re.sub(r'(?i)[^0-9]*', '', response.url)
        if len(self.user_id) != 8:
            return 3
        try:
            csrf_token = re.findall(r'<meta name="csrf-token" content="(\w.+)">', response.text)[0]
        except Exception as e:
            print(e)
        if not csrf_token:
            return 3
        self.httpSession.headers.update({'x-csrf-token': csrf_token})
        self.httpSession.headers.update({'x-requested-with': 'XMLHttpRequest'})
        return 0

    def getRequestList(self, user_id = None):
        if not user_id:
            user_id = self.user_id
        n, res = self._post(f"https://helpdesk.efko.ru/tasks/user/allowed-break-task", params = {'userCode': user_id, 'per-page': 200})
        if (n == 0 and res != None):
            #count_task = re.findall(r'<h2>.+\(.(\d+).\)</h2>', res)[0]
            soup = BeautifulSoup(res.text.replace('\\"', '"'), 'lxml')
            res = soup.find_all('tr')
            new_list = []
            for task in res[2:]:
                item = {'isRun': False}
                if 'current-task-row' in task.attrs['class']:
                    item['isRun'] = True
                body = task.find_all('td')
                links = body[0].find_all('a')
                item['request_id'] = links[0].get_text()
                item['initiator_name'] = links[1].get_text()
                item['initiator_id'] = re.sub(r'(?i)[^0-9]*', '', links[1].get('href'))
                item['task_id'] = body[1].find_all('div', {'class': 'task-description-code'})[0].get_text()
                item['task_text'] = body[1].find_all('div', {'class': 'task-description'})[0].get_text(separator = '\n', strip = True)
                item['task_date'] = body[2].get_text()
                item['task_type'] = body[3].get_text('|').split('|')[1]
                item['task_time'] = body[4].get_text(strip=True)
                item['task_plan'] = body[5].get_text(strip=True)
                item['task_wait'] = body[6].find_all('div', {'class': 'text-center'})[0].get_text(strip=True)
                new_list.append(item)
            return True, new_list
        return False, None

    def stopTask(self, task_id, request_id):
        """Остановка задачи, ответ от сервера при успешной остановке {"status":1,"message":""}"""

        n, res = self._post(f"https://helpdesk.efko.ru/tasks/tool/stop", params = {'code': task_id, 'task': request_id})
        if (n == 0 and res != None):
            res = res.json()
            if res.get('status') == 1:
                return True, res.get('message')
            return False, 'Непредвиденный ответ от сервера'
        return False, 'Ошибка сервера'

    def runTask(self, task_id, request_id, callback):
        n, res = self._post(f"https://helpdesk.efko.ru/tasks/tool/run", params = {'code': task_id, 'task': request_id})
        if (n == 0 and res != None):
            res = res.json()
            if res.get('status') == 2:
                soup = BeautifulSoup(res.get('message'), 'lxml')
                _csrf = soup.find('input', {'name': '_csrf'}).get('value')
                title = soup.find('h3', {'class': 'panel-title'}).get_text(strip = True)
                buf = soup.find('div', {'class': 'panel-body'})
                buf = soup.find_all('li')
                task_list = []
                for task in buf:
                    task_list.append(task.get_text(strip = True))
                callback(title, task_list, _csrf)
                return 2, None
            if res.get('status') == 1:
                return 1, res.get('message')
            return 0, 'Непредвиденный ответ от сервера'
        return 0, 'Ошибка сервера'

    def runTaskConfirm(self, task_id, request_id, _csrf, msg):
        if len(msg) >= 3:
            n, res2 = self._post(f"https://helpdesk.efko.ru/tasks/tool/run", params = {'code': task_id, 'task': request_id},
                data = {'_csrf': _csrf, 'StartTaskForm[reasonForSkipping]': msg})
            if (n == 0 and res2 != None):
                res2 = res2.json()
                if res2.get('status') == 1:
                    return True, res2.get('message')
                return False, 'Непредвиденный ответ от сервера'
            return False, 'Ошибка сервера'
        return False, 'Ошибка при запуске задачи'

    def getInitiatorInfo(self, id):
        n, res = self._post(f"https://helpdesk.efko.ru/tasks/user/information", params = {'userCode': id})
        if (n == 0 and res != None):
            soup = BeautifulSoup(res.text.replace('\\"', '"'), 'lxml')
            res = soup.find_all('td')
            list = []
            for item in res[0:5]:
                list.append(item.get_text(strip = True))
            return True, list
        return False, 'Ошибка сервера'

    def loadAnswer(self, task_id):
        n, res = self._get("https://helpdesk.efko.ru/tasks/view/feedback", params = {'code': task_id, 'all': 1})
        if (n == 0 and res != None):
            soup = BeautifulSoup(res.text, 'lxml')
            res = soup.find_all('div', {'class': 'task-feedback-wrapper'})
            list = []
            for item in res:
                author = item.find('span', {'class': 'task-feedback-author-name'}).get_text(strip = True)
                date = item.find('span', {'class': 'task-feedback-date'}).get_text(strip = True)
                text = item.find('div', {'class': 'task-feedback-text'}).get_text(strip = True)
                list.insert(0, {'author': author, 'date': date, 'text': text})
            return True, list
        return False, 'Ошибка сервера'

    def getRequestText(self, request_id):
        n, res = self._get("https://helpdesk.efko.ru/tasks/view", params = {'code': request_id})
        if (n == 0 and res != None):
            soup = BeautifulSoup(res.text, 'lxml')
            soup = soup.find('div', {'class': 'task-description-block'})
            text = soup.find('div', {'class': 'panel-body'}).get_text(strip = True)
            return True, text
        return False, 'Ошибка сервера'

    def getRequestCard(self, request_id):
        n, res = self._get("https://helpdesk.efko.ru/tasks/view/card", params = {'code': request_id})
        if (n == 0 and res != None):
            soup = BeautifulSoup(res.text, 'lxml')
            res = soup.find_all('tr')
            card = []
            for line in res:
                title = line.find('th').get_text(strip=True)
                text = line.find('td').get_text(strip=True)
                card.append({'title': title, 'text': text})
            return True, card
        return False, 'Ошибка сервера'

    def getTaskList(self, request_id):
        n, res = self._get("https://helpdesk.efko.ru/tasks/view/task-list", params = {'code': request_id})
        if (n == 0 and res != None):
            soup = BeautifulSoup(res.text, 'lxml')
            tbody = soup.find('tbody')
            lines = tbody.find_all('tr')
            task_list = []
            for line in lines[2:]:
                item = {'isRun': False}
                if 'current-task-row' in line.attrs['class']:
                    item['isRun'] = True
                body = line.find_all('td')
                item['task_id'] = body[0].find('a').get_text()
                item['task_text'] = body[0].find('div', {'class': 'task-description'}).get_text(separator = '\n', strip = True)
                item['result'] = body[1].get_text(separator = '\n', strip = True)
                item['task_date'] = body[2].get_text(strip=True)
                item['task_date_end'] = body[3].get_text(strip=True)
                item['responsible'] = body[4].get_text()
                item['responsible_id'] = re.sub(r'(?i)[^0-9]*', '', body[4].find('a').get('href'))
                item['task_type'] = body[5].get_text('|').split('|')[1]
                item['task_time'] = body[7].get_text(strip=True)
                item['task_plan'] = body[8].get_text(strip=True)
                item['task_wait'] = body[9].find_all('div', {'class': 'text-center'})[0].get_text(strip=True)
                task_list.append(item)
            return True, task_list
        return False, 'Ошибка сервера'

    def getFilesList(self, request_id):
        n, res = self._get("https://helpdesk.efko.ru/tasks/view/request-files", params = {'code': request_id})
        if (n == 0 and res != None):
            soup = BeautifulSoup(res.text, 'lxml')
            links = soup.find_all('a')
            files_list = []
            for link in links:
                local = False
                if 'text-gray' in link.attrs['class']:
                    local = True
                href = link.get('href')
                title = link.get_text(strip=True)
                if title == 'Добавить':
                    continue
                files_list.append({'title': title, 'local': local, 'href': href})
            return True, files_list
        return False, 'Ошибка сервера'