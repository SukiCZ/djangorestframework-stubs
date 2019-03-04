from collections import OrderedDict
from typing import Any, Dict, Optional

from mypy.nodes import Expression, SymbolTableNode, TypeInfo
from mypy.plugin import CheckerPluginInterface, ClassDefContext
from mypy.types import AnyType, Instance, Type, TypeOfAny, TypedDictType, deserialize_map
from mypy_django_plugin import helpers as django_helpers
# noinspection PyUnresolvedReferences
from mypy_django_plugin.helpers import get_argument_by_name, get_argument_type_by_name, get_assigned_value_for_class, \
    get_model_fullname_from_string, get_nested_meta_node_for_current_class, has_any_of_bases, is_none_expr, is_optional, \
    iter_over_assignments, make_optional, make_required, parse_bool, reparametrize_instance


FIELD_FULLNAME = 'rest_framework.fields.Field'
BASE_SERIALIZER_FULLNAME = 'rest_framework.serializers.BaseSerializer'
SERIALIZER_FULLNAME = 'rest_framework.serializers.Serializer'
LIST_SERIALIZER_FULLNAME = 'rest_framework.serializers.ListSerializer'
MODEL_SERIALIZER_FULLNAME = 'rest_framework.serializers.ModelSerializer'

# TODO: finish mapping
SERIALIZER_FIELD_MAPPING = {
    'django.db.models.fields.AutoField': 'rest_framework.serializers.IntegerField',
    'django.db.models.fields.BigIntegerField': 'rest_framework.serializers.IntegerField',
    'django.db.models.fields.BooleanField': 'rest_framework.serializers.BooleanField',
    'django.db.models.fields.CharField': 'rest_framework.serializers.CharField',
    'django.db.models.fields.CommaSeparatedIntegerField': 'rest_framework.serializers.CharField',
    'django.db.models.fields.DateField': 'rest_framework.serializers.DateField',
    'django.db.models.fields.DateTimeField': 'rest_framework.serializers.DateTimeField',
    'django.db.models.fields.DecimalField': 'rest_framework.serializers.DecimalField',
}
ID_TYPE = 'builtins.object'


def get_field_type(typ: Instance, primitive: bool = False) -> Type:
    if primitive:
        return typ.args[1]
    else:
        return typ.args[0]


def deserialize_type(api: CheckerPluginInterface, data: Dict[str, Any]) -> Type:
    if isinstance(data, str):
        return api.named_generic_type(data, [])

    classname = data['.class']
    deserialize = deserialize_map.get(classname)
    if not deserialize:
        return AnyType(TypeOfAny.from_error)
    return deserialize(data)


def get_type_for_model_field(model_field_type: Instance,
                             api: CheckerPluginInterface,
                             use_primitive_types: bool = False) -> Type:
    field_type_fullname = SERIALIZER_FIELD_MAPPING.get(model_field_type.type.fullname())
    if not field_type_fullname:
        return AnyType(TypeOfAny.explicit)

    field_type = api.named_generic_type(field_type_fullname, [])
    types = get_drf_metadata_key(field_type.type, 'types', traverse_mro=True)
    if types:
        if use_primitive_types:
            typ_data = types['primitive']
        else:
            typ_data = types['actual']
        typ = deserialize_type(api, typ_data)
        return typ

    return AnyType(TypeOfAny.explicit)


def is_autogenerated_primary_key(sym: SymbolTableNode) -> bool:
    return sym and isinstance(sym.type, Instance) and sym.type.type.fullname() == ID_TYPE


def get_corresponding_typeddict(serializer_type: Instance,
                                api: CheckerPluginInterface,
                                use_primitive_types: bool = False) -> TypedDictType:
    typeddict_items = OrderedDict()  # type: OrderedDict[str, Type]
    for base in reversed(serializer_type.type.mro):
        for name, sym in base.names.items():
            if name in typeddict_items:
                continue
            typ = sym.type
            if isinstance(typ, Instance) and typ.type.has_base(FIELD_FULLNAME):
                typeddict_items[name] = get_field_type(typ, primitive=use_primitive_types)

    if serializer_type.type.has_base(MODEL_SERIALIZER_FULLNAME):
        base_model_fullname = get_drf_metadata(serializer_type.type).get('base_model')
        if base_model_fullname is not None:
            base_model_type = api.named_generic_type(base_model_fullname, []).type
            defined_model_fields = get_drf_metadata(serializer_type.type).get('fields', [])
            for field_name in defined_model_fields:
                if field_name not in typeddict_items:
                    sym = base_model_type.get(field_name)
                    if field_name == 'id' and is_autogenerated_primary_key(sym):
                        typeddict_items[field_name] = api.named_generic_type('builtins.int', [])
                        continue

                    if sym and isinstance(sym.type, Instance) and sym.type.type.has_base(django_helpers.FIELD_FULLNAME):
                        typeddict_items[field_name] = get_type_for_model_field(sym.type, api=api)

    return TypedDictType(items=typeddict_items,
                         required_keys=set(typeddict_items.keys()),
                         fallback=api.named_generic_type('builtins.dict', [api.named_generic_type('builtins.str', []),
                                                                           AnyType(TypeOfAny.explicit)]))


def get_drf_metadata(info: TypeInfo) -> Dict[str, Any]:
    return info.metadata.setdefault('drf', {})


def get_drf_metadata_key(info: TypeInfo,
                         key: str,
                         traverse_mro: bool = False) -> Optional[Any]:
    infos_to_check = [info]
    if traverse_mro:
        infos_to_check = info.mro

    for base in infos_to_check:
        metadata = get_drf_metadata(base)
        if key in metadata:
            return metadata[key]

    return None


def get_meta_attribute_value(ctx: ClassDefContext, attr_name: str) -> Optional[Expression]:
    meta_info = get_nested_meta_node_for_current_class(ctx.cls.info)
    if meta_info is None:
        return None

    return get_assigned_value_for_class(meta_info, attr_name)
