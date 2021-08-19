from __future__ import annotations

from typing import Optional, List, Dict

from pydantic import BaseModel


class Request(BaseModel):
    url: str
    method: str
    headers: Dict[str, str]
    referrerPolicy: str
    isSameSite: Optional[bool]


class CallFrame(BaseModel):
    functionName: str
    url: str
    lineNumber: int
    columnNumber: int


class StackTrace(BaseModel):
    description: Optional[str]
    callFrames: List[CallFrame]
    parent: Optional[StackTrace]


StackTrace.update_forward_refs()


class Initiator(BaseModel):
    type: str
    stack: Optional[StackTrace]
    url: Optional[str]
    lineNumber: Optional[str]
    columnNumber: Optional[str]


class RequestInfo(BaseModel):
    documentURL: str
    request: Request
    initiator: Initiator
    type: Optional[str]
