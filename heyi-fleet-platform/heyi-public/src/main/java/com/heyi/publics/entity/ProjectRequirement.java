package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 车头 / 挂车需求明细行。type：tractor / trailer。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_project_requirement")
public class ProjectRequirement extends BaseEntity {

    private Long projectId;
    private String type;
    private String model;
    private String battery;
    private Integer qty;
}
