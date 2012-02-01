"""
Subscription handling (consider moving to nsa.py, it practially a DTO)

Author: Henrik Thostrup Jensen <htj@nordu.net>
Copyright: NORDUnet (2012)
"""



class Subscription:

    def __init__(self, event, system, data):
        self.event  = event
        self.system = system
        self.data   = data


    def match(self, event):
        return self.event == event



def dispatchNotification(success, result, subscription, event_registry):

    handler = event_registry.getHandler(subscription.event, subscription.system)
    return handler(success, result, subscription.data)

