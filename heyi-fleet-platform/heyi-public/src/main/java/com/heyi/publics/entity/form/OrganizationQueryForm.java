package com.heyi.publics.entity.form;

import lombok.Data;

@Data
public class OrganizationQueryForm {

    private String name;
    private String type;
    private Long parentId;
}
