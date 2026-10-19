package com.heyi.publics.common.base;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 实体基类：主键由代码显式赋值（IdType.INPUT），逻辑删除字段 deleted_at（毫秒时间戳，0 表示未删除）。
 */
@Data
public class BaseEntity {

    @TableId(type = IdType.INPUT)
    private Long id;

    /** 创建人（由 @DynamicUserFields 切面填充） */
    @TableField(fill = FieldFill.INSERT)
    private String createdBy;

    /** 更新人（由 @DynamicUserFields 切面填充） */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private String updatedBy;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    /** 逻辑删除：0 未删除，删除时写入毫秒时间戳 */
    private Long deletedAt;
}
