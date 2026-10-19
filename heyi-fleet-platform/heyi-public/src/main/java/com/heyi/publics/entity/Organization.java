package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 组织 / 部门（含全公司 CO 与项目公司 project）。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("sys_organization")
public class Organization extends BaseEntity {

    private String name;
    /** company / dept / team / project */
    private String type;
    private Long parentId;
    private String head;
    private Integer depth;
    private Integer sortOrder;
}
