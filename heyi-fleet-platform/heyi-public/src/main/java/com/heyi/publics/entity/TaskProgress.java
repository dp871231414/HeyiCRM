package com.heyi.publics.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.heyi.publics.common.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 任务进展时间轴（只能追加，不可直改历史）。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biz_task_progress")
public class TaskProgress extends BaseEntity {

    private Long taskId;
    private String content;
}
