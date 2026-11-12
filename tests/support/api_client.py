"""One location for workflow routes and demo identity headers."""
class ClaimsClient:
    def __init__(self,client,actor="customer-m100"):
        self.client,self.actor=client,actor
    @property
    def headers(self):return {"X-Demo-Actor":self.actor}
    def as_actor(self,actor):return ClaimsClient(self.client,actor)
    def submit(self,**changes):
        payload={"claim_id":"API-100","member_id":"M100","service":"medical","amount_cents":100000,**changes}
        return self.client.post("/api/claims",json=payload,headers=self.headers)
    def transition(self,claim_id,target):return self.client.post(f"/api/claims/{claim_id}/transitions",json={"target":target},headers=self.headers)
    def get(self,claim_id):return self.client.get(f"/api/claims/{claim_id}",headers=self.headers)
    def list(self):return self.client.get("/api/claims",headers=self.headers)
