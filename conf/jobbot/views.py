from django.shortcuts import render
from django.utils import timezone
from django.urls import resolve
from rest_framework.views import APIView
from rest_framework.response import Response

from . import env

import io
import os
import re
import sys
import time
import ctypes
import signal
import datetime
import threading
import numpy as np
import pandas as pd
from slack_sdk import WebClient
from timeit import default_timer as timer

class JobBot(APIView):
	def __init__(self):
		self.token = env.token
		self.ch_name = env.ch_name
		self.client = WebClient(self.token)

		self.job_id = -1

	def PrintMsg(self, text):
		self.client.chat_postMessage(
			channel=self.ch_name,
			text='<@%s> ' % self.user_name_ + text 
		)

	def PrintWatcher(self, qstat):
		if qstat['user'] in list(env.user_dict) and self.user_name_ != env.user_dict[qstat['user']]:
			self.client.chat_postMessage(
				channel=self.ch_name,
				text='<@%s> 님이 <@%s> 님의 잡이 언제 끝날지 궁금해합니다...\n' % (self.user_name_, env.user_dict[qstat['user']])
			)

	def GetQ(self):
		qstat_str = os.popen('%s \"qstat -u \'*\' -xml | tr \'\\n\' \' \' | sed \'s#<job_list[^>]*>#\\n#g\' | sed \'s#<[^>]*>##g\' | grep \' \' | column -t\"' % env.server).read()

		if len(qstat_str) < 1: return 0, 'j0'
		else:
			qstat_arr = []
			for qs in qstat_str.split('\n')[:-1]:
				qs_s = qs.split()
				if len(qs_s) < 8: qs_s.insert(-1, 'NaN')
				qstat_arr.append(qs_s)

			qstat = pd.DataFrame(
					qstat_arr,
					columns=['job_id', 'prior', 'name', 'user', 'state', 'submit_time', 'queue', 'slots'],
					)
			qstat['job_id'] = qstat['job_id'].astype('i')
			qstat['submit_time'] = pd.to_datetime(qstat['submit_time'])
			qstat['elapsed_time'] = (timezone.now() - qstat['submit_time']).dt.total_seconds() / 60

			if self.job_id not in qstat['job_id'].to_list(): return 0, 'j1'
			elif qstat.loc[qstat['job_id'] == self.job_id, 'state'].iloc[0] == 'Eqw': return 0, 'j2'
			else: return qstat, ''

	def GetQInfo(self, qstat):
		return '\t'.join([qstat['name'], qstat['user'], qstat['queue'], qstat['slots']]), qstat['elapsed_time']

	def RunJobBot(self):
		t0 = timer()

		while True:
			qstat_tot, err = self.GetQ()
			if len(err) < 1:
				qstat = qstat_tot[qstat_tot['job_id'] == self.job_id].iloc[0, :]
				print(datetime.datetime.now(), self.user_name_, self.trigger_id_, 'Running', '%fs' % (timer()-t0))
				time.sleep(env.time_itv)
			else:
				if err == 'j1':
					t1 = timer()
					self.PrintMsg('%d\t%s\t(약 %d분 소요)\n위 잡이 완료되었습니다.' % (self.job_id, *self.GetQInfo(qstat)))
					print(datetime.datetime.now(), self.user_name_, self.trigger_id_, 'Done', '%fs' % (timer()-t0), end='\n\n')
					break
				else:
					self.Error(err)
					break

	def post(self, request):
		print(datetime.datetime.now(), request.body.decode('utf-8').split('&'))

		self.user_name_  = request.data['user_name']
		self.trigger_id_ = request.data['trigger_id']

		args_list = request.data['text'].split()

		if len(args_list) < 1:
			self.Error('a0')
		else: 
			self.job_id = int(args_list[0])

			if re.match('/jobbot/run/', request.path_info):
				qstat_tot, err = self.GetQ()
				if len(err): self.Error(err)
				else:
					threading.Thread(target=self.RunJobBot, args=[]).start()
					qstat = qstat_tot[qstat_tot['job_id'] == self.job_id].iloc[0, :]
					self.PrintMsg('%d\t%s\t(현재 %d분 경과)\n위 잡에 대한 알림 설정이 완료되었습니다.' % (self.job_id, *self.GetQInfo(qstat)))
					self.PrintWatcher(qstat)
			elif re.match('/jobbot/exit/', request.path_info):
				res = 2
				if res > 1: self.PrintMsg('알림 설정이 취소되지 않았습니다.\n')
				else: self.PrintMsg('알림 설정이 정상적으로 취소되었습니다.\n')
			else:
				print('%s is wrong path.' % request.path_info)
				sys.exit(1)

		return Response(status=200)

	def Error(self, err_type):
		err_dict = {
			'a0': '잡 ID를 입력하세요. 사용법: /jb [job_id]',
			'j0': '현재 제출된 잡이 없습니다.',
			'j1': '%d 은(는) 존재하지 않는 잡 ID 입니다.' % self.job_id,
			'j2': '%d 은(는) Eqw 상태 입니다. 알림 설정을 할 수 없습니다.' % self.job_id,
		}
		self.PrintMsg('%s\n' % err_dict[err_type])
		print('Error')
