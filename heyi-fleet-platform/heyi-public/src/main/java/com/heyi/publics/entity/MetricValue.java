package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;

/**
 * 指标目标值 / 实际值。kind：target / actual；period 如 2026 或 2026-10。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_metric_value")
public class MetricValue extends BaseEntity {

    private Long metricId;
    private Long orgId;
    private String period;
    private String kind;
    private BigDecimal value;
}
