from rest_framework import serializers

from apps.core.exceptions import ErroConflitoHorario
from apps.core.utils import valor_efetivo

from .models import Consulta


class ConsultaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consulta
        fields = ["id", "data_hora", "profissional", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # O DRF geraria automaticamente um UniqueTogetherValidator a partir da
        # UniqueConstraint do model, que dispararia antes de validate() abaixo e
        # levantaria rest_framework.exceptions.ValidationError diretamente — violando
        # RN-15 (erro de conflito de horário deve ser ErroConflitoHorario, exceção de
        # domínio). Desativado aqui; a constraint de banco continua como segunda
        # barreira (Guard B.2, SDD-03).
        validators = []

    def validate(self, dados):
        profissional = valor_efetivo(dados, self.instance, "profissional")
        data_hora = valor_efetivo(dados, self.instance, "data_hora")

        conflito = Consulta.objects.filter(profissional=profissional, data_hora=data_hora)
        if self.instance:
            conflito = conflito.exclude(pk=self.instance.pk)

        if conflito.exists():
            # Exceção de domínio, não rest_framework.exceptions.ValidationError diretamente
            # (ver CONVENCOES-CODIGO.md, seção 4) — tratar_erro_global traduz para 400.
            raise ErroConflitoHorario(
                profissional_id=str(profissional.pk) if profissional else None,
                data_hora=data_hora,
            )
        return dados
