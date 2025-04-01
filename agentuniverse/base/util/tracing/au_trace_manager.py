# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2025/1/3 14:13
# @Author  : fanen.lhy
# @Email   : fanen.lhy@antgroup.com
# @FileName: trace_manager.py
from contextvars import ContextVar, Token
from agentuniverse.base.context.framework_context_manager import \
    FrameworkContextManager
from agentuniverse.base.util.tracing.au_trace_context import AuTraceContext
from agentuniverse.base.annotation.singleton import singleton


@singleton
class AuTraceManager:
    def __init__(self, context_class=None):
        self.context_class = context_class or AuTraceContext
        self.context_instance = ContextVar("__au_trace_context__")

    def set_context_class(self, context_class):
        self.context_class = context_class

    def reset_trace(self):
        self.context_instance.set(None)

    @property
    def trace_context(self) -> AuTraceContext:
        context = self.context_instance.get(None)
        if not context:
            context = self.context_class.new_context()
            self.context_instance.set(context)
        return context

    def get_trace_dict(self) -> dict:
        trace_dict = {}
        if self.trace_context.session_id:
            trace_dict["session_id"] = self.trace_context.session_id
        if self.trace_context.trace_id:
            trace_dict["trace_id"] = self.trace_context.trace_id
        if self.trace_context.span_id:
            trace_dict["span_id"] = self.trace_context.span_id
        return trace_dict

    def set_session_id(self, session_id):
        self.trace_context.set_session_id(session_id)

    def get_session_id(self):
        return self.trace_context.trace_id

    def set_trace_id(self, trace_id):
        self.trace_context.set_trace_id(trace_id)

    def get_trace_id(self):
        return self.trace_context.trace_id

    def set_span_id(self, span_id):
        self.trace_context.set_span_id(span_id)

    def get_span_id(self):
        return self.trace_context.span_id
