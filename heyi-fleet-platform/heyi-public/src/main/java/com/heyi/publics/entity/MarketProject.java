package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 市场项目（商机）。车头/挂车需求为后端按子表重算的汇总值。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_market_project")
public class MarketProject extends BaseEntity {

    private String name;
    private String description;
    private Integer stage;
    private Long ownerId;
    private String ownerName;
    private Long ownerDeptId;
    private Integer tractorDemand;
    private Integer trailerDemand;
    /** 最新一条进展冗余快照 */
    private String progress;
}
