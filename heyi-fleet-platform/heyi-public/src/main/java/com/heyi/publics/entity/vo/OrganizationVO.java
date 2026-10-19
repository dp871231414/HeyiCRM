package com.heyi.publics.entity.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class OrganizationVO {

    private Long id;
    private String name;
    private String type;
    private Long parentId;
    private String head;
    private Integer depth;
    private Integer sortOrder;
    private LocalDateTime createdAt;
    private String createdBy;
}
