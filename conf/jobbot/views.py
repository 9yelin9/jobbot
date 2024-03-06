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
import json
import time
import ctypes
import signal
import datetime
import threading
import xmltodict
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

    def PrintWatcher(self, job):
        if job['JB_owner'] in list(env.user_dict) and self.user_name_ != env.user_dict[job['JB_owner']]:
            self.client.chat_postMessage(
                    channel=self.ch_name,
                    text=':meow_party:\t<@%s> 님이 <@%s> 님의 잡이 언제 끝날지 궁금해합니다...\n' % (self.user_name_, env.user_dict[job['JB_owner']])
                    )

    def GetJob(self):
        qstat_xml = os.popen('%s \"qstat -u \'*\' -xml\"' % env.server).read()
        qstat_dict = json.loads(json.dumps(xmltodict.parse(qstat_xml)))['job_info']

        job_list = []
        for info in [qstat_dict['queue_info'], qstat_dict['job_info']]:
            if info != None:
                for job in np.ravel(info['job_list']): job_list.append(job)

        for i, job in enumerate(job_list):
            if int(job['JB_job_number']) == self.job_id:
                if job['@state'] == 'running':
                    job['elapsed_time'] = (datetime.datetime.now() - datetime.datetime.strptime(job['JAT_start_time'], '%Y-%m-%dT%H:%M:%S')).total_seconds() / 60 
                    return job, ''
                else:
                    job['elapsed_time'] = 0
                    return job, 'j1'

        return {}, 'j0'

    def GetJobInfo(self, job):
        return '\t'.join([str(job[v]) for v in ['JB_name', 'JB_owner', 'queue_name', 'slots']]), job['elapsed_time']

    def RunJobBot(self):
        print(datetime.datetime.now(), self.user_name_, self.trigger_id_, 'Start')

        job, err = self.GetJob()
        if len(job):
            self.PrintMsg(':bell:\t%d\t%s\t(현재 %d분 경과)\n알림이 설정되었습니다.' % (self.job_id, *self.GetJobInfo(job)))
            if len(err): self.Error(err)
            self.PrintWatcher(job)

            t0 = timer()
            while True:
                job_new, err = self.GetJob()
                if len(job_new):
                    job = job_new
                    time.sleep(env.time_itv)
                else:
                    self.PrintMsg(':white_check_mark:\t%d\t%s\t(약 %d분 소요)\n잡이 완료되었습니다.' % (self.job_id, *self.GetJobInfo(job)))
                    print(datetime.datetime.now(), self.user_name_, self.trigger_id_, 'Done', '%fs' % (timer()-t0), end='\n\n')
                    break
        else: self.Error(err)

    def post(self, request):
        print(datetime.datetime.now(), request.body.decode('utf-8').split('&'))

        self.user_name_  = request.data['user_name']
        self.trigger_id_ = request.data['trigger_id']

        args_list = request.data['text'].split()

        if len(args_list) < 1:
            self.Error('a0')
        elif args_list[0].isdecimal() != True:
            self.Error('a0')
        else: 
            self.job_id = int(args_list[0])
            if re.match('/jobbot/run/', request.path_info):
                threading.Thread(target=self.RunJobBot, args=[]).start()
            else:
                print('%s is wrong path' % request.path_info)
                sys.exit(1)

        return Response(status=200)

    def Error(self, err):
        err_dict = {
                'a0': '잡 ID를 입력하세요. 사용법: /jb [job_id]',
                'j0': '%d 은(는) 존재하지 않는 잡 ID 입니다.' % self.job_id,
                'j1': '%d 은(는) 현재 대기 중입니다.' % self.job_id,
                }
        self.PrintMsg(':meow_party:\t%s\n' % err_dict[err])
        print(datetime.datetime.now(), self.user_name_, self.trigger_id_, 'Error %s\n' % err)
