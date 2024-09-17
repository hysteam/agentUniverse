# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2024/7/18 21:08
# @Author  : wangchongshi
# @Email   : wangchongshi.wcs@antgroup.com
# @FileName: sql_alchemy_memory.py
from abc import abstractmethod
import json
from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import declarative_base
from sqlalchemy import Integer, String, DateTime, Text, Column, Index, and_, func

from agentuniverse.agent.memory.memory import Memory
from agentuniverse.agent.memory.message import Message
from agentuniverse.base.config.component_configer.configers.memory_configer import MemoryConfiger
from agentuniverse.base.util.memory_util import get_memory_tokens
from agentuniverse.database.sqldb_wrapper import SQLDBWrapper
from agentuniverse.database.sqldb_wrapper_manager import SQLDBWrapperManager


class BaseMemoryConverter(BaseModel):
    """Convert BaseMemory to the SQLAlchemy model."""

    model_class: Any = None
    model_config = ConfigDict(protected_namespaces=())

    @abstractmethod
    def from_sql_model(self, sql_message: Any) -> Message:
        """Convert a SQLAlchemy model to a Message instance."""
        raise NotImplementedError

    @abstractmethod
    def to_sql_model(self, message: Message, session_id: str) -> Any:
        """Convert a Message instance to a SQLAlchemy model."""
        raise NotImplementedError

    @abstractmethod
    def get_sql_model_class(self) -> Any:
        """Get the SQLAlchemy model class."""
        raise NotImplementedError


def create_memory_model(table_name: str, DynamicBase: Any) -> Any:
    """
    Create a memory model for a given table name.

    Args:
        table_name: The name of the table to use.
        DynamicBase: The base class to use for the model.

    Returns:
        The model class.
    """

    class MemoryModel(DynamicBase):
        """The default memory model for SqlAlchemyMemory."""
        __tablename__ = table_name
        id = Column(Integer, primary_key=True, autoincrement=True)
        session_id = Column(String(100), default='')
        agent_id = Column(String(100), default='')
        source = Column(String(500), default='')
        message = Column(Text)
        gmt_created = Column(DateTime, default=func.now())
        gmt_modified = Column(DateTime, default=func.now(), onupdate=func.now())

        __table_args__ = (
            Index('memory_ix_session_id', 'session_id'),
            Index('memory_ix_agent_id_source', 'agent_id', 'source'),
        )

    return MemoryModel


class DefaultMemoryConverter(BaseMemoryConverter):
    """The default memory converter for SqlAlchemyMemory."""

    def __init__(self, table_name: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.model_class = create_memory_model(table_name, declarative_base())

    def from_sql_model(self, sql_message: Any) -> Message:
        """Convert a SQLAlchemy model to a Message instance."""
        return Message.from_dict(json.loads(sql_message.message))

    def to_sql_model(self, message: Message, session_id: str = None, agent_id: str = None, source: str = None) -> Any:
        """Convert a Message instance to a SQLAlchemy model."""
        return self.model_class(
            session_id=session_id, agent_id=agent_id, source=source,
            message=json.dumps(message.to_dict(), ensure_ascii=False)
        )

    def get_sql_model_class(self) -> Any:
        """Get the SQLAlchemy model class."""
        return self.model_class


class SqlAlchemyMemory(Memory):
    """SqlAlchemyMemory class that stores messages in a SQL database.

    Long-term memory: it is a long-term memory that stores messages in a SQL database.

    Attributes:
        sqldb_table_name (str): The name of the table to store for the memory.
        sqldb_wrapper_name (str): The name of the SQLDBWrapper to use for the memory.
        memory_converter (BaseMemoryConverter): The memory converter to use for the memory.
        _sqldb_wrapper (SQLDBWrapper): The SQLDBWrapper instance to use for the memory.
    """

    sqldb_table_name: Optional[str] = 'memory'
    sqldb_wrapper_name: Optional[str] = None
    memory_converter: BaseMemoryConverter = None
    _sqldb_wrapper: SQLDBWrapper = None

    def delete(self, session_id: str = '', agent_id: str = '', **kwargs) -> None:
        """Delete the memory from the database."""
        if self._sqldb_wrapper is None:
            self._init_db()
        with self._sqldb_wrapper.get_session()() as session:
            model_class = self.memory_converter.get_sql_model_class()
            query = session.query(model_class)

            # construct query based on the provided session_id and agent_id
            if session_id:
                query = query.filter(getattr(model_class, 'session_id') == session_id)
            if agent_id:
                query = query.filter(getattr(model_class, 'agent_id') == agent_id)

            # execute delete and commit the session
            query.delete(synchronize_session=False)
            session.commit()

    def add(self, message_list: List[Message], session_id: str = '', agent_id: str = '', **kwargs) -> None:
        """Add messages to the memory db."""
        if self._sqldb_wrapper is None:
            self._init_db()
        if message_list is None:
            return
        with self._sqldb_wrapper.get_session()() as session:
            for message in message_list:
                session.add(
                    self.memory_converter.to_sql_model(message=message, session_id=session_id, agent_id=agent_id,
                                                       source=message.source))
            session.commit()

    def get(self, session_id: str = '', agent_id: str = '', source: str = '', top_k=None, **kwargs) -> List[Message]:
        """Get messages from the memory db."""
        if self._sqldb_wrapper is None:
            self._init_db()
        with self._sqldb_wrapper.get_session()() as session:
            # get the messages from the memory by session_id and agent_id
            model_class = self.memory_converter.get_sql_model_class()
            conditions = []

            # conditionally add session_id to the query
            if session_id:
                session_id_col = getattr(model_class, 'session_id')
                conditions.append(session_id_col == session_id)

            # conditionally add agent_id to the query
            if agent_id:
                agent_id_col = getattr(model_class, 'agent_id')
                conditions.append(agent_id_col == agent_id)

            # conditionally add source to the query
            if source:
                source_col = getattr(model_class, 'source')
                conditions.append(source_col == source)

            # build the query with dynamic conditions
            query = session.query(self.memory_converter.model_class)
            if conditions:
                query = query.where(and_(*conditions))
            query = query.order_by(model_class.gmt_created.asc())

            # Execute the query and fetch the results
            records = query.all()

            if top_k is not None:
                records = records[-top_k:]

            messages = []
            for record in records:
                messages.append(self.memory_converter.from_sql_model(record))

            # prune messages
            return self.prune(messages, self.llm_name)

    def prune(self, message_list: List[Message], llm_name: str, **kwargs) -> List[Message]:
        """Prune messages from the memory due to memory max token limitation."""
        if len(message_list) < 1:
            return []
        new_messages = message_list[:]
        # get the number of tokens of the session messages.
        tokens = get_memory_tokens(new_messages, llm_name)
        # truncate the memory if it exceeds the maximum number of tokens
        if tokens > self.max_tokens:
            prune_messages = []
            while tokens > self.max_tokens:
                prune_messages.append(new_messages.pop(0))
                tokens = get_memory_tokens(new_messages, llm_name)
            summarized_memory = self.summarize_memory(prune_messages, self.max_tokens - tokens)
            if summarized_memory:
                new_messages.insert(0, Message(content=summarized_memory))
        return new_messages

    def initialize_by_component_configer(self, component_configer: MemoryConfiger) -> 'SqlAlchemyMemory':
        """Initialize the memory by the ComponentConfiger object.
        Args:
            component_configer(MemoryConfiger): the ComponentConfiger object
        Returns:
            SqlAlchemyMemory: the SqlAlchemyMemory object
        """
        super().initialize_by_component_configer(component_configer)
        if 'sqldb_wrapper_name' in component_configer.configer.value:
            self.sqldb_wrapper_name = component_configer.configer.value.get('sqldb_wrapper_name', '')
        if self.sqldb_wrapper_name is None:
            raise Exception('`sqldb_wrapper_name` is not set')
        if 'sqldb_table_name' in component_configer.configer.value:
            self.sqldb_table_name = component_configer.configer.value.get('sqldb_table_name', '')
        # initialize the memory converter if not set
        if self.memory_converter is None:
            self.memory_converter = DefaultMemoryConverter(self.sqldb_table_name)
        return self

    def _init_db(self) -> None:
        """Initialize the database."""
        self._sqldb_wrapper = SQLDBWrapperManager().get_instance_obj(self.sqldb_wrapper_name)
        if self._sqldb_wrapper is None:
            raise Exception('The sqldb_wrapper for the `sqldb_wrapper_name` was not found,'
                            ' please check the `sqldb_wrapper_name`.')
        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self) -> None:
        """Create the db table if it does not exist."""
        with self._sqldb_wrapper.sql_database._engine.connect() as conn:
            if not conn.dialect.has_table(conn, self.sqldb_table_name):
                self.memory_converter.get_sql_model_class().__table__.create(conn)
