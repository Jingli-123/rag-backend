from dotenv import load_dotenv

load_dotenv()
import os
import httpx
from fastapi import Request
from clerk_backend_api import Clerk
from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions


def is_signed_in(request: Request):
    sdk = Clerk(bearer_auth=os.getenv('CLERK_SECRET_KEY'))
    request_state = sdk.authenticate_request(
        request,
        AuthenticateRequestOptions(
            authorized_parties=[ 
                party for party in [
                    os.getenv("FRONT_END_URL"),
                    os.getenv("FRONT_END_DOMAIN_URL")
                    ]
                if party
            ]
        )
    )
    # print("SECRET", os.getenv("CLERK_SECRET_KEY")[:15])
    # print("SIGNED IN:", request_state.is_signed_in)
    # print("STATE:", request_state)
    return request_state.is_signed_in