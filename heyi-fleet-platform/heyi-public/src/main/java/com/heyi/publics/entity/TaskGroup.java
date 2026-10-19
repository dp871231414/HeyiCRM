package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 任务组：唯一性为「名称 + 所属责任人」联合唯一；系统内置「空」任务组不可删。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_task_group")
public class TaskGroup extends BaseEntity {

    private String name;
    private Long ownerId;
    private String ownerName;
    private Integer isSystem;
}
