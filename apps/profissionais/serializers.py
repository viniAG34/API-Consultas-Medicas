from rest_framework import serializers

from apps.core.exceptions import ErroValidacao
from apps.core.utils import valor_efetivo

from .models import Profissional


class ProfissionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profissional
        fields = [
            "id",
            "nome_social",
            "profissao",
            "registro_profissional",
            "email",
            "telefone",
            "logradouro",
            "numero",
            "bairro",
            "cidade",
            "estado",
            "cep",
            "complemento",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        help_text="Email de contato. Obrigatório se telefone não for informado (RN-03).",
    )
    telefone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
        help_text="Telefone de contato. Obrigatório se email não for informado (RN-03).",
    )

    def validate(self, dados):
        email = valor_efetivo(dados, self.instance, "email", "")
        telefone = valor_efetivo(dados, self.instance, "telefone", "")
        if not email and not telefone:
            # Exceção de domínio, não rest_framework.exceptions.ValidationError diretamente
            # (ver CONVENCOES-CODIGO.md, seção 4) — RN-03 do SDD-03 é regra de negócio,
            # mesmo tratamento dado ao conflito de horário em ConsultaSerializer.
            raise ErroValidacao(
                "Informe ao menos um meio de contato: email ou telefone.",
                campo="contato",
            )
        return dados
