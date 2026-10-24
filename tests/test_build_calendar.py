import unittest
from datetime import datetime, timezone, timedelta
from scripts.build_calendar import normalize_openfootball, normalize_espn, create_snapshot, daily_espn_url

NOW = datetime(2026,10,24,15,0,tzinfo=timezone.utc)

class CalendarPipelineTests(unittest.TestCase):
    def test_openfootball_handles_known_and_unknown_kickoff(self):
        raw={'matches':[
            {'date':'2026-10-25','time':'14:00','team1':'Liverpool','team2':'Arsenal'},
            {'date':'2026-10-26','team1':'Chelsea','team2':'Everton'},
            {'date':'2026-10-15','team1':'Chelsea','team2':'Everton','score':{'ft':[2,1]}}
        ]}
        fi, hist=normalize_openfootball(raw,'eng.1', NOW-timedelta(days=1),NOW+timedelta(days=12),NOW)
        self.assertEqual(len(fi),2)
        self.assertEqual(fi[0]['utc'],'2026-10-25T14:00:00Z')
        self.assertIsNone(fi[1]['utc'])
        self.assertTrue(fi[1]['timeTBD'])
        self.assertEqual(len(hist),1)
    def test_espn_filters_completed(self):
        def match(id,state):
            return {'id':id,'date':'2026-10-27T23:00Z','status':{'type':{'state':state,'completed':state=='post'}},
              'competitions':[{'competitors':[{'homeAway':'home','team':{'displayName':'Bulls'}},
                                             {'homeAway':'away','team':{'displayName':'Celtics'}}]}]}
        fi=normalize_espn({'events':[match('1','pre'),match('2','post')]},'nba')
        self.assertEqual(len(fi),1)
        self.assertEqual(fi[0]['sport'],'basket')
    def test_espn_only_one_date(self):
        u=daily_espn_url('nfl',datetime(2026,10,24,tzinfo=timezone.utc))
        self.assertIn('dates=20261024&',u)
    def test_snapshot_merges_sources_without_inventing_games(self):
        def open_data(lid,start,end,now):
            if lid!='eng.1':return lid,[],[],[]
            return lid,[{'id':'x','competitionId':lid,'league':'Premier League','sport':'football','home':'A','away':'B','date':'2026-10-28','utc':None,'timeTBD':True,'status':'pre','source':'OpenFootball','finished':False}],[],[]
        def espn_data(lid,start,end):return lid,[],1,[]
        x=create_snapshot(NOW,days=10,getter_open=open_data,getter_espn=espn_data)
        self.assertEqual(x['schema'],1)
        self.assertEqual(len(x['fixtures']),1)
        self.assertEqual(x['diagnostics']['nba']['days_ok'],1)

if __name__=='__main__':unittest.main()
