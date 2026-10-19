package com.heyi.publics.entity.vo;

import lombok.Data;

import java.util.List;

@Data
public class RoleVO {

    private Long id;
    private String name;
    private String description;
    private String scope;
    private List<String> permissions;
    private Integer isSystem;
}
