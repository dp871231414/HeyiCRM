package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 角色：scope 为数据可见范围（self/dept/dept_sub/all），permissions 为菜单+按钮权限集合。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("sys_role")
public class Role extends BaseEntity {

    private String name;
    private String description;
    private String scope;
    /** JSON 数组字符串，存放权限 key */
    private String permissions;
    /** 内置角色受删除保护 */
    private Integer isSystem;
}
