"""sprint 16.4 v1.5 — 法律文书模板 + 渲染产物

Revision ID: 19004v15
Revises: 19003v15
Create Date: 2026-05-06 22:00:00.000000

新表：legal_document_template + legal_document_render
种子：4 条平台默认模板（律师函/调解通知/诉状大纲/代理委托）
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '19004v15'
down_revision: str | None = '19003v15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LAWYER_LETTER_TPL = """\
# 催款律师函

**致**：{{owner_name}}

**地址**：{{owner_address}}

**事由**：物业服务费催收

---

兹有委托人 **{{tenant_name}}** 委托本所就阁下拖欠物业服务费一事，特此函告如下：

阁下与{{tenant_name}}签订的《物业服务合同》约定，阁下应按时缴纳物业服务费。
然截至 {{today_date}} 止，阁下尚欠物业费人民币 **¥{{amount_owed}}**（{{months_overdue}} 个月），
经我方多次电话催收（共 {{total_calls}} 通通话）仍未缴纳。

依据《中华人民共和国民法典》第九百四十四条之规定，
业主应按约定向物业服务人支付物业费，违反约定的，物业服务人可以起诉催收。

**特此函告**：请阁下于本函送达之日起 **15 日内**，向{{tenant_name}}缴清上述欠款。
逾期未缴，本所将代表委托人依法向人民法院提起诉讼，由此产生的诉讼费、
律师费、保全费等一切费用将由阁下承担。

特此函告，望阁下慎重处理。

---

委托律师：**{{lawyer_name}}**
执业律所：**{{firm_name}}**
日期：{{today_date}}
"""

MEDIATION_TPL = """\
# 物业费纠纷诉前调解通知

**致**：{{owner_name}}

我所受 **{{tenant_name}}** 委托，就阁下与该物业公司之间的物业费纠纷
（欠费金额 **¥{{amount_owed}}**，逾期 {{months_overdue}} 个月）
启动诉前调解程序。

**调解流程**：
1. 律师将于近日致电与阁下联系，了解情况
2. 协助双方就争议事项进行沟通（如服务质量异议、付款方式、分期方案等）
3. 达成一致 → 出具《调解协议》并代为送达；未达成一致 → 转入诉讼

调解期间，本所建议阁下保留与物业的所有沟通记录、缴费凭证、报修记录等证据。

**承办律师**：{{lawyer_name}}
**联系方式**：本所将于 3 个工作日内主动联系
**律所**：{{firm_name}}
**日期**：{{today_date}}
"""

SMALL_CLAIMS_TPL = """\
# 小额诉讼协助 — 诉状大纲

**原告**：{{tenant_name}}
**被告**：{{owner_name}}
**案由**：物业服务合同纠纷
**诉讼标的**：人民币 **¥{{amount_owed}}** 元

---

## 一、诉讼请求

1. 判令被告向原告支付物业服务费 **¥{{amount_owed}}** 元；
2. 判令被告向原告支付逾期滞纳金（按欠费金额日息万分之五计算，自欠费之日起至实际支付之日止）；
3. 本案诉讼费由被告承担。

## 二、事实与理由

原告系 [小区名称] 物业服务公司，被告系该小区 {{owner_address}} 房屋业主。
被告与原告签订《物业服务合同》，应按时缴纳物业服务费。

被告自 [起始月份] 起至今未缴物业费，截至起诉之日累计欠费 **¥{{amount_owed}}** 元，
逾期 {{months_overdue}} 个月。原告先后通过电话催收 **{{total_calls}}** 通、
书面通知 [N] 次，被告均未履行付款义务。

## 三、证据清单

1. 《物业服务合同》原件
2. 被告房产证明
3. 物业费账单及缴费记录
4. 催收通话录音及书面通知（已区块链存证）
5. 物业服务质量证明材料

## 四、办理建议

- 提交法院：被告所在地基层法院
- 适用程序：小额诉讼程序（标的额 < 5 万元，可适用简易速裁）
- 预估周期：受理后 30-60 日

---

**协助律师**：{{lawyer_name}}（{{firm_name}}）
**日期**：{{today_date}}
"""

FULL_AGENCY_TPL = """\
# 法律服务委托代理协议（要点）

**委托人**：{{tenant_name}}
**受托人**：{{firm_name}}（承办律师 {{lawyer_name}}）

---

## 一、委托事项

委托受托人就委托人与业主 {{owner_name}}（{{owner_address}}）的物业费纠纷
（欠费金额 **¥{{amount_owed}}**），全程代理至下列阶段终结：
1. 调解 / 和解
2. 起诉、应诉、反诉
3. 一审、二审、再审
4. 强制执行

## 二、代理权限

特别授权（含代为承认、放弃、变更诉讼请求，进行和解，提起反诉或上诉，代为收款等）。

## 三、收费方式（基础费 + 风险代理）

- 基础律师费：免（成功分成模式）
- 成功分成：按实际回款额的 **20%** 收取
- 法院诉讼费、保全费、鉴定费等由委托人据实承担

## 四、其他

- 本案历史催收记录（共 {{total_calls}} 通通话录音）已通过区块链存证，
  委托人授权受托人调取作为证据使用
- 协议有效期至执行终结之日

---

**签订日期**：{{today_date}}
"""


def upgrade() -> None:
    op.create_table(
        'legal_document_template',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
        sa.Column('package_type', sa.String(32), nullable=False),
        sa.Column('slug', sa.String(64), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "package_type IN ('lawyer_letter','mediation','small_claims','full_agency')",
            name='ck_legal_doc_tpl_pkg_type',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'package_type', 'slug',
            name='uq_legal_doc_tpl_tenant_pkg_slug',
        ),
    )
    op.create_index(
        'ix_legal_document_template_tenant_id', 'legal_document_template', ['tenant_id']
    )

    op.create_table(
        'legal_document_render',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('template_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('rendered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('rendered_by', sa.BigInteger(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['legal_conversion_order.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['legal_document_template.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rendered_by'], ['user_account.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_legal_document_render_order_id', 'legal_document_render', ['order_id']
    )
    op.create_index(
        'ix_legal_doc_render_order_version',
        'legal_document_render', ['order_id', 'version']
    )

    # Seed 4 platform default templates
    for pkg, slug, title, body in [
        ('lawyer_letter', 'default', '催款律师函', LAWYER_LETTER_TPL),
        ('mediation', 'default', '物业费纠纷诉前调解通知', MEDIATION_TPL),
        ('small_claims', 'default', '小额诉讼协助 — 诉状大纲', SMALL_CLAIMS_TPL),
        ('full_agency', 'default', '法律服务委托代理协议', FULL_AGENCY_TPL),
    ]:
        op.execute(
            sa.text("""
                INSERT INTO legal_document_template
                  (tenant_id, package_type, slug, title, body_md, enabled, version)
                VALUES
                  (NULL, :pkg, :slug, :title, :body, TRUE, 1)
            """).bindparams(pkg=pkg, slug=slug, title=title, body=body)
        )


def downgrade() -> None:
    op.drop_index('ix_legal_doc_render_order_version', table_name='legal_document_render')
    op.drop_index('ix_legal_document_render_order_id', table_name='legal_document_render')
    op.drop_table('legal_document_render')
    op.drop_index('ix_legal_document_template_tenant_id', table_name='legal_document_template')
    op.drop_table('legal_document_template')
