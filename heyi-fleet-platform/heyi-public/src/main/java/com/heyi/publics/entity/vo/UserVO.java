package com.heyi.publics.entity.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class UserVO {

    private Long id;
    private String name;
    private String account;
    private Long deptId;
    private String deptName;
    private Long roleId;
    private String roleName;
    private String scope;
    private String status;
    private LocalDateTime lastLoginAt;
}
