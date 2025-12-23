from pydantic import BaseModel

class AntiPatternInput(BaseModel):
    architecture_pattern: str
    architecture_confidence: float
    loc: float
    methods: float
    classes: float
    avg_cc: float
    imports: float
    annotations: float
    controller_deps: float
    service_deps: float
    repository_deps: float
    entity_deps: float
    adapter_deps: float
    port_deps: float
    usecase_deps: float
    gateway_deps: float
    total_cross_layer_deps: float
    has_business_logic: bool
    has_data_access: bool
    has_http_handling: bool
    has_validation: bool
    has_transaction: bool
    violates_layer_separation: bool
