def valor_efetivo(dados: dict, instancia, campo: str, default=None):
    """
    Resolve o valor efetivo de um campo em validate() de serializer, considerando
    tanto criação (instancia=None) quanto atualização parcial (PATCH — campo pode
    não vir em `dados`, mas já existir na instância). Usado por ProfissionalSerializer
    e ConsultaSerializer para validação combinada de campos (CONVENCOES-CODIGO.md).
    """
    return dados.get(campo, getattr(instancia, campo, default))
