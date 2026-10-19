package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDate;

/**
 * 任务。完成进度由系统计算（done/target），不手填百分比。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_task")
public class Task extends BaseEntity {

    private String name;
    private Long taskGroupId;
    private String description;
    private Integer abnormal;
    private java.math.BigDecimal target;
    private java.math.BigDecimal done;
    private String unit;
    private LocalDate startDate;
    private LocalDate endDate;
    private Long deptId;
    private Long ownerId;
    private String ownerName;
    /** 最新一条进展冗余快照 */
    private String progress;
}
