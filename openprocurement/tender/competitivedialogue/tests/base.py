# -*- coding: utf-8 -*-
import os
import webtest
from hashlib import sha512
from datetime import datetime, timedelta
from uuid import uuid4
from copy import deepcopy
from openprocurement.api.tests.base import BaseTenderWebTest, PrefixedRequestClass
from openprocurement.api.utils import apply_data_patch
from openprocurement.api.models import get_now, SANDBOX_MODE
from openprocurement.tender.openeu.models import (TENDERING_DURATION, QUESTIONS_STAND_STILL,
                                                  COMPLAINT_STAND_STILL)

from openprocurement.tender.openeu.tests.base import (test_tender_data as base_test_tender_data_eu,
                                                      test_features_tender_data,
                                                      test_bids,
                                                      test_bids as test_bids_eu)
from openprocurement.tender.competitivedialogue.models import CD_EU_TYPE, CD_UA_TYPE, STAGE_2_EU_TYPE, STAGE_2_UA_TYPE
from openprocurement.api.design import sync_design
from openprocurement.api.tests.base import PrefixedRequestClass, test_organization
from openprocurement.tender.openua.tests.base import (test_tender_data as base_test_tender_data_ua, BaseTenderWebTest)

now = datetime.now()
test_tender_data_eu = deepcopy(base_test_tender_data_eu)
test_tender_data_eu["procurementMethodType"] = CD_EU_TYPE
test_tender_data_ua = deepcopy(base_test_tender_data_eu)
del test_tender_data_ua["title_en"]
test_tender_data_ua["procurementMethodType"] = CD_UA_TYPE
test_tender_data_ua["tenderPeriod"]["endDate"] = (now + timedelta(days=31)).isoformat()


# stage 2
test_tender_stage2_data_eu = deepcopy(base_test_tender_data_eu)
test_tender_stage2_data_ua = deepcopy(base_test_tender_data_ua)
test_tender_stage2_data_eu["procurementMethodType"] = STAGE_2_EU_TYPE
test_tender_stage2_data_ua["procurementMethodType"] = STAGE_2_UA_TYPE
test_tender_stage2_data_eu["procurementMethod"] = "selective"
test_tender_stage2_data_ua["procurementMethod"] = "selective"
test_shortlistedFirms = [
    {
        "identifier": {"scheme": test_organization["identifier"]['scheme'],
                       "id": u'00037257',
                       "uri": test_organization["identifier"]['uri']},
        "name": "Test org name 1"
    },
    {
        "identifier": {"scheme": test_organization["identifier"]['scheme'],
                       "id": u'00037257',
                       "uri": test_organization["identifier"]['uri']},
        "name": "Test org name 2"
    },
    {
        "identifier": {"scheme": test_organization["identifier"]['scheme'],
                       "id": u'00037257',
                       "uri": test_organization["identifier"]['uri']},
        "name": "Test org name 3"
    },
]
test_access_token_stage1 = uuid4().hex
test_tender_stage2_data_eu["shortlistedFirms"] = test_shortlistedFirms
test_tender_stage2_data_ua["shortlistedFirms"] = test_shortlistedFirms
test_tender_stage2_data_eu["dialogue_token"] = sha512(test_access_token_stage1).hexdigest()
test_tender_stage2_data_ua["dialogue_token"] = sha512(test_access_token_stage1).hexdigest()
test_tender_stage2_data_ua["owner"] = "broker"
test_tender_stage2_data_eu["owner"] = "broker"
test_tender_stage2_data_ua["status"] = "draft"
test_tender_stage2_data_eu["status"] = "draft"
test_tender_stage2_data_ua["tenderPeriod"]["endDate"] = (now + timedelta(days=31)).isoformat()
test_tender_stage2_data_eu["tenderPeriod"]["endDate"] = (now + timedelta(days=31)).isoformat()
test_tender_stage2_data_ua["dialogueID"] = uuid4().hex
test_tender_stage2_data_eu["dialogueID"] = uuid4().hex
test_tender_stage2_data_ua["items"][0]["classification"]["scheme"] = "CPV"
test_tender_stage2_data_eu["items"][0]["classification"]["scheme"] = "CPV"

test_lots = [
    {
        'title': 'lot title',
        'description': 'lot description',
        'value': test_tender_data_eu['value'],
        'minimalStep': test_tender_data_eu['minimalStep'],
    }
]


if SANDBOX_MODE:
    test_tender_data_eu['procurementMethodDetails'] = 'quick, accelerator=1440'
    test_tender_data_ua['procurementMethodDetails'] = 'quick, accelerator=1440'


class BaseCompetitiveDialogWebTest(BaseTenderWebTest):
    initial_data = None
    initial_status = None
    initial_bids = None
    initial_lots = None
    initial_auth = None
    relative_to = os.path.dirname(__file__)

    def go_to_enquiryPeriod_end(self):
        now = get_now()
        self.set_status('active.tendering', {
            "enquiryPeriod": {
                "startDate": (now - timedelta(days=28)).isoformat(),
                "endDate": (now - (timedelta(minutes=1) if SANDBOX_MODE else timedelta(days=1))).isoformat()
            },
            "tenderPeriod": {
                "startDate": (now - timedelta(days=28)).isoformat(),
                "endDate": (now + (timedelta(minutes=2) if SANDBOX_MODE else timedelta(days=2))).isoformat()
            }
        })

    def setUp(self):
        super(BaseTenderWebTest, self).setUp()
        if self.docservice:
            self.setUpDS()
        if self.initial_auth:
            self.app.authorization = self.initial_auth
        else:
            self.app.authorization = ('Basic', ('broker', ''))

    def tearDown(self):
        if self.docservice:
            self.setUpDS()
        self.couchdb_server.delete(self.db_name)
        self.couchdb_server.create(self.db_name)
        db = self.couchdb_server[self.db_name]
        # sync couchdb views
        sync_design(db)
        self.app.app.registry.db = db
        self.db = self.app.app.registry.db

    def check_chronograph(self):
        authorization = self.app.authorization
        self.app.authorization = ('Basic', ('chronograph', ''))
        response = self.app.patch_json('/tenders/{}'.format(self.tender_id), {'data': {'id': self.tender_id}})
        self.app.authorization = authorization
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')

    def time_shift(self, status, extra=None):
        now = get_now()
        tender = self.db.get(self.tender_id)
        data = {}
        if status == 'enquiryPeriod_ends':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=28)).isoformat(),
                    "endDate": (now - timedelta(days=1)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=28)).isoformat(),
                    "endDate": (now + timedelta(days=2)).isoformat()
                },
            })
        if status == 'active.pre-qualification':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION).isoformat(),
                    "endDate": (now).isoformat(),
                }
            })
        elif status == 'active.pre-qualification.stand-still':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION).isoformat(),
                    "endDate": (now).isoformat(),
                },
                "qualificationPeriod": {
                    "startDate": (now).isoformat(),
                },
            })
            if 'lots' in tender and tender['lots']:
                data['lots'] = []
                for index, lot in enumerate(tender['lots']):
                    lot_data = {'id': lot['id']}
                    if lot['status'] is 'active':
                        lot_data["auctionPeriod"] = {
                            "startDate": (now + COMPLAINT_STAND_STILL).isoformat()
                        }
                    data['lots'].append(lot_data)
            else:
                data.update({
                    "auctionPeriod": {
                        "startDate": (now + COMPLAINT_STAND_STILL).isoformat()
                    }
                })
        elif status == 'active.auction':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - TENDERING_DURATION + QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL).isoformat()
                },
                "qualificationPeriod": {
                    "startDate": (now - COMPLAINT_STAND_STILL).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if 'lots' in tender and tender['lots']:
                data['lots'] = []
                for index, lot in enumerate(tender['lots']):
                    lot_data = {'id': lot['id']}
                    if lot['status'] == 'active':
                        lot_data["auctionPeriod"] = {
                            "startDate": (now).isoformat()
                        }
                    data['lots'].append(lot_data)
            else:
                data.update({
                    "auctionPeriod": {
                        "startDate": now.isoformat()
                    }
                })
        elif status == 'complete':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=3)).isoformat(),
                    "endDate": (now - timedelta(days=2)).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=3)).isoformat(),
                                "endDate": (now - timedelta(days=2)).isoformat()
                            }
                        }
                        for i in self.initial_lots
                    ]
                })
        if extra:
            data.update(extra)
        tender.update(apply_data_patch(tender, data))
        self.db.save(tender)

    def set_status(self, status, extra=None):
        data = {'status': status}
        if status == 'active.tendering':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now + TENDERING_DURATION - QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now + TENDERING_DURATION).isoformat()
                }
            })
        elif status == 'active.pre-qualification':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - timedelta(days=1)).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat(),
                },
                "qualificationPeriod": {
                    "startDate": (now).isoformat(),
                }
            })
        elif status == 'active.qualification':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=2)).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL - COMPLAINT_STAND_STILL - timedelta(days=1)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=2)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - timedelta(days=1)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=1)).isoformat(),
                                "endDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.pre-qualification.stand-still':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - timedelta(days=1)).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat(),
                },
                "qualificationPeriod": {
                    "startDate": (now).isoformat(),
                },
                "auctionPeriod": {
                    "startDate": (now + COMPLAINT_STAND_STILL).isoformat()
                }
            })
        elif status == 'active.stage2.pending':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=1)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - TENDERING_DURATION + QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=1)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL).isoformat()
                },
                "qualificationPeriod": {
                    "startDate": (now - COMPLAINT_STAND_STILL).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.auction':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=1)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - TENDERING_DURATION + QUESTIONS_STAND_STILL).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=1)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL).isoformat()
                },
                "qualificationPeriod": {
                    "startDate": (now - COMPLAINT_STAND_STILL).isoformat(),
                    "endDate": (now).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.awarded':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL - COMPLAINT_STAND_STILL - timedelta(days=2)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - timedelta(days=2)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=2)).isoformat(),
                    "endDate": (now - timedelta(days=1)).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=2)).isoformat(),
                                "endDate": (now - timedelta(days=1)).isoformat()
                            }
                        }
                        for i in self.initial_lots
                    ]
                })
        elif status == 'complete':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=4)).isoformat(),
                    "endDate": (now - QUESTIONS_STAND_STILL - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - TENDERING_DURATION - COMPLAINT_STAND_STILL - timedelta(days=4)).isoformat(),
                    "endDate": (now - COMPLAINT_STAND_STILL - timedelta(days=3)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=3)).isoformat(),
                    "endDate": (now - timedelta(days=2)).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=3)).isoformat(),
                                "endDate": (now - timedelta(days=2)).isoformat()
                            }
                        }
                        for i in self.initial_lots
                    ]
                })
        if extra:
            data.update(extra)

        tender = self.db.get(self.tender_id)
        tender.update(apply_data_patch(tender, data))
        self.db.save(tender)

        authorization = self.app.authorization
        self.app.authorization = ('Basic', ('chronograph', ''))
        # response = self.app.patch_json('/tenders/{}'.format(self.tender_id), {'data': {'id': self.tender_id}})
        response = self.app.get('/tenders/{}'.format(self.tender_id))
        self.app.authorization = authorization
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        return response


class BaseCompetitiveDialogEUStage2WebTest(BaseCompetitiveDialogWebTest):
    initial_data = test_tender_stage2_data_eu


class BaseCompetitiveDialogUAStage2WebTest(BaseCompetitiveDialogWebTest):
    initial_data = test_tender_stage2_data_ua

    def set_status(self, status, extra=None):
        data = {'status': status}
        if status == 'active.tendering':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now).isoformat(),
                    "endDate": (now + timedelta(days=13)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now).isoformat(),
                    "endDate": (now + timedelta(days=16)).isoformat()
                }
            })
        elif status == 'active.auction':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=16)).isoformat(),
                    "endDate": (now - timedelta(days=3)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=16)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.qualification':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=4)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=1)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=1)).isoformat(),
                                "endDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.awarded':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=4)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=1)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=1)).isoformat(),
                                "endDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'complete':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=25)).isoformat(),
                    "endDate": (now - timedelta(days=11)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=25)).isoformat(),
                    "endDate": (now - timedelta(days=8)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=8)).isoformat(),
                    "endDate": (now - timedelta(days=7)).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now - timedelta(days=7)).isoformat(),
                    "endDate": (now - timedelta(days=7)).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=8)).isoformat(),
                                "endDate": (now - timedelta(days=7)).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        if extra:
            data.update(extra)

        tender = self.db.get(self.tender_id)
        tender.update(apply_data_patch(tender, data))
        self.db.save(tender)

        authorization = self.app.authorization
        self.app.authorization = ('Basic', ('chronograph', ''))
        response = self.app.get('/tenders/{}'.format(self.tender_id))
        self.app.authorization = authorization
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        return response


class BaseCompetitiveDialogEUWebTest(BaseCompetitiveDialogWebTest):
    initial_data = test_tender_data_eu


class BaseCompetitiveDialogUAWebTest(BaseCompetitiveDialogWebTest):
    initial_data = test_tender_data_ua


class BaseCompetitiveDialogUAContentWebTest(BaseCompetitiveDialogUAWebTest):
    initial_data = test_tender_data_ua
    initial_status = None
    initial_bids = None
    initial_lots = None

    def setUp(self):
        self.app.authorization = ('Basic', ('broker', ''))
        super(BaseCompetitiveDialogUAContentWebTest, self).setUp()
        self.create_tender()


class BaseCompetitiveDialogEUContentWebTest(BaseCompetitiveDialogEUWebTest):
    initial_data = test_tender_data_eu
    initial_status = None
    initial_bids = None
    initial_lots = None

    def setUp(self):
        self.app.authorization = ('Basic', ('broker', ''))
        super(BaseCompetitiveDialogEUContentWebTest, self).setUp()
        self.create_tender()


def create_tender_stage2(self, initial_lots=None, initial_data=None, features=None, initial_bids=None):
    if initial_lots is None:
        initial_lots = self.initial_lots
    if initial_data is None:
        initial_data = self.initial_data
    if initial_bids is None:
        initial_bids = self.initial_bids
    auth = self.app.authorization
    self.app.authorization = ('Basic', ('competitive_dialogue', ''))
    data = deepcopy(initial_data)
    if initial_lots:  # add lots
        lots = []
        for i in initial_lots:
            lot = deepcopy(i)
            if 'id' not in lot:
                lot['id'] = uuid4().hex
            lots.append(lot)
        data['lots'] = self.lots = lots
        for i, item in enumerate(data['items']):
            item['relatedLot'] = lots[i % len(lots)]['id']
        for firm in data['shortlistedFirms']:
            firm['lots'] = [dict(id=lot['id']) for lot in lots]
        self.lots_id = [lot['id'] for lot in lots]
    if features:  # add features
        for feature in features:
            if feature['featureOf'] == 'lot':
                feature['relatedItem'] = data['lots'][0]['id']
            if feature['featureOf'] == 'item':
                feature['relatedItem'] = data['items'][0]['id']
        data['features'] = self.features = features
    response = self.app.post_json('/tenders', {'data': data})  # create tender
    tender = response.json['data']
    status = response.json['data']['status']
    self.tender = tender
    self.tender_token = response.json['access']['token']
    self.tender_id = tender['id']
    self.app.authorization = ('Basic', ('competitive_dialogue', ''))
    self.app.patch_json('/tenders/{id}?acc_token={token}'.format(id=self.tender_id,
                                                                 token=self.tender_token),
                        {'data': {'status': 'draft.stage2'}})

    self.app.authorization = ('Basic', ('broker', ''))
    self.app.patch_json('/tenders/{id}?acc_token={token}'.format(id=self.tender_id,
                                                                 token=self.tender_token),
                        {'data': {'status': 'active.tendering'}})
    self.app.authorization = auth
    if initial_bids:
        self.initial_bids_tokens = {}
        response = self.set_status('active.tendering')
        status = response.json['data']['status']
        bids = []
        for i in initial_bids:
            if initial_lots:
                i = i.copy()
                value = i.pop('value')
                i['lotValues'] = [
                    {
                        'value': value,
                        'relatedLot': l['id'],
                    }
                    for l in self.lots
                    ]
            response = self.app.post_json('/tenders/{}/bids'.format(self.tender_id), {'data': i})
            self.assertEqual(response.status, '201 Created')
            bids.append(response.json['data'])
            self.initial_bids_tokens[response.json['data']['id']] = response.json['access']['token']
        self.bids = bids
    if self.initial_status and self.initial_status != status:
        self.set_status(self.initial_status)


class BaseCompetitiveDialogEUStage2ContentWebTest(BaseCompetitiveDialogEUWebTest):
    initial_data = test_tender_stage2_data_eu
    initial_status = None
    initial_bids = None
    initial_lots = None
    initial_features = None

    def setUp(self):
        self.app.authorization = ('Basic', ('broker', ''))
        super(BaseCompetitiveDialogEUStage2ContentWebTest, self).setUp()
        self.create_tender()

    create_tender = create_tender_stage2


class BaseCompetitiveDialogUAStage2ContentWebTest(BaseCompetitiveDialogUAWebTest):
    initial_data = test_tender_stage2_data_ua
    initial_status = None
    initial_bids = None
    initial_lots = None
    initial_features = None

    def create_tenderers(self, count=1):
        tenderers = []
        for i in xrange(count):
            tenderer = deepcopy(test_bids[0]["tenderers"])
            tenderer[0]['identifier']['id'] = self.initial_data['shortlistedFirms'][i if i < 3 else 3]['identifier'][
                'id']
            tenderer[0]['identifier']['scheme'] = \
                self.initial_data['shortlistedFirms'][i if i < 3 else 3]['identifier']['scheme']
            tenderers.append(tenderer)
        return tenderers

    def setUp(self):
        self.app.authorization = ('Basic', ('broker', ''))
        super(BaseCompetitiveDialogUAStage2ContentWebTest, self).setUp()
        self.create_tender()

    create_tender = create_tender_stage2

    def set_status(self, status, extra=None):
        data = {'status': status}
        if status == 'active.tendering':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now).isoformat(),
                    "endDate": (now + timedelta(days=13)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now).isoformat(),
                    "endDate": (now + timedelta(days=16)).isoformat()
                }
            })
        elif status == 'active.auction':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=16)).isoformat(),
                    "endDate": (now - timedelta(days=3)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=16)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.qualification':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=4)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=1)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=1)).isoformat(),
                                "endDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'active.awarded':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=4)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=17)).isoformat(),
                    "endDate": (now - timedelta(days=1)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=1)).isoformat(),
                    "endDate": (now).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now).isoformat(),
                    "endDate": (now).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=1)).isoformat(),
                                "endDate": (now).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        elif status == 'complete':
            data.update({
                "enquiryPeriod": {
                    "startDate": (now - timedelta(days=25)).isoformat(),
                    "endDate": (now - timedelta(days=11)).isoformat()
                },
                "tenderPeriod": {
                    "startDate": (now - timedelta(days=25)).isoformat(),
                    "endDate": (now - timedelta(days=8)).isoformat()
                },
                "auctionPeriod": {
                    "startDate": (now - timedelta(days=8)).isoformat(),
                    "endDate": (now - timedelta(days=7)).isoformat()
                },
                "awardPeriod": {
                    "startDate": (now - timedelta(days=7)).isoformat(),
                    "endDate": (now - timedelta(days=7)).isoformat()
                }
            })
            if self.initial_lots:
                data.update({
                    'lots': [
                        {
                            "auctionPeriod": {
                                "startDate": (now - timedelta(days=8)).isoformat(),
                                "endDate": (now - timedelta(days=7)).isoformat()
                            }
                        }
                        for i in self.initial_lots
                        ]
                })
        if extra:
            data.update(extra)

        tender = self.db.get(self.tender_id)
        tender.update(apply_data_patch(tender, data))
        self.db.save(tender)

        authorization = self.app.authorization
        self.app.authorization = ('Basic', ('chronograph', ''))
        response = self.app.get('/tenders/{}'.format(self.tender_id))
        self.app.authorization = authorization
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        return response

test_features_tender_eu_data = test_features_tender_data.copy()
test_features_tender_eu_data['procurementMethodType'] = CD_EU_TYPE

author = deepcopy(test_bids[0]["tenderers"][0])
author['identifier']['id'] = test_shortlistedFirms[0]['identifier']['id']
author['identifier']['scheme'] = test_shortlistedFirms[0]['identifier']['scheme']
