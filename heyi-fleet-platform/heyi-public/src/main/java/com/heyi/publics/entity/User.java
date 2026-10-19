package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDateTime;

/**
 * 账号。密码以 BCrypt 加盐哈希存储，任何接口不得返回 passwordHash。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("sys_user")
public class User extends BaseEntity {

    private String name;
    private String account;
    private String passwordHash;
    private Long deptId;
    private Long roleId;
    /** 空表示跟随角色默认范围 */
    private String scope;
    /** active / disabled */
    private String status;
    private LocalDateTime lastLoginAt;
    private String lastLoginIp;
}
