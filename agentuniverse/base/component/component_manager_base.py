# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2024/3/14 15:46
# @Author  : jerry.zzw 
# @Email   : jerry.zzw@antgroup.com
# @FileName: component_manager_base.py
import copy
from typing import TypeVar, Generic

from agentuniverse.base.config.application_configer.application_config_manager import ApplicationConfigManager
from agentuniverse.base.component.component_base import ComponentBase
from agentuniverse.base.component.component_enum import ComponentEnum

# 添加类型范型限定
ComponentTypeVar = TypeVar("ComponentTypeVar", bound=ComponentBase)


class ComponentManagerBase(Generic[ComponentTypeVar]):
    """The ComponentManagerBase class, which is used to define the base class of the component manager."""

    def __init__(self, component_type: ComponentEnum):
        """Initialize the ComponentManagerBase."""
        # The component pool map, which is used to store the component instance.
        # _instance_obj_map - Format: {component_instance_name: component_instance_obj}.
        self._instance_obj_map: dict[str, ComponentTypeVar] = {}
        self._component_type: ComponentEnum = component_type

    def register(self, component_instance_name: str, component_instance_obj: ComponentTypeVar):
        """Register the component instance."""
        if component_instance_name in self._instance_obj_map.keys():
            raise ValueError(f"{self._component_type.value} component object instance with name "
                             f"'{component_instance_name}' already exists.")
        self._instance_obj_map[component_instance_name] = component_instance_obj

    def unregister(self, component_instance_name: str):
        """Unregister the component instance abstractmethod."""
        self._instance_obj_map.pop(component_instance_name)

    def get_instance_obj(self, component_instance_name: str,
                         appname: str = None, new_instance: bool = False) -> ComponentTypeVar:
        """Return the component instance object."""
        appname = appname or ApplicationConfigManager().app_configer.base_info_appname
        instance_code = f'{appname}.{self._component_type.value.lower()}.{component_instance_name}'
        if new_instance:
            return copy.deepcopy(self._instance_obj_map.get(instance_code))
        return self._instance_obj_map.get(instance_code)

    def get_instance_name_list(self) -> list[str]:
        """Return the component instance list."""
        return list(self._instance_obj_map.keys())

    def get_instance_obj_list(self) -> list[ComponentTypeVar]:
        """Return the component instance object list."""
        return list(self._instance_obj_map.values())
