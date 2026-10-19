package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 文档中心文档。分组可见范围由角色 doc_groups 控制（两级权限）。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("sys_doc")
public class SystemDoc extends BaseEntity {

    private String docKey;
    private String title;
    private String docGroup;
    private String content;
    private Integer version;
}
