package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;

/**
 * 指标定义。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_metric_def")
public class MetricDef extends BaseEntity {

    private String code;
    private String name;
    private String unit;
    /** annual / project / monitor */
    private String metricGroup;
    private String family;
    /** positive / negative */
    private String direction;
    private String cycle;
    private Integer weight;
    private BigDecimal warn;
    private BigDecimal danger;
    private BigDecimal rateTarget;
    private Integer isSnapshot;
    private Integer noTarget;
    private Long ownerOrgId;
}
