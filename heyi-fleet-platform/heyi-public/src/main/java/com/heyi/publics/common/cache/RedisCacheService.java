package com.heyi.publics.common.cache;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Set;
import java.util.function.Supplier;

/**
 * 基于 StringRedisTemplate 的缓存实现，value 用 Jackson 存 JSON。
 */
@Slf4j
@Service("cacheService")
@RequiredArgsConstructor
public class RedisCacheService implements CacheService {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    @Value("${app.cache-prefix:lb}")
    private String prefix;

    @Override
    public String key(String biz, Object... parts) {
        StringBuilder sb = new StringBuilder(prefix).append(':').append(biz);
        if (parts != null) {
            for (Object p : parts) {
                sb.append(':').append(p == null ? "" : p.toString());
            }
        }
        return sb.toString();
    }

    @Override
    public <T> T get(String key, Class<T> type) {
        try {
            String json = redisTemplate.opsForValue().get(key);
            if (json == null) {
                return null;
            }
            return objectMapper.readValue(json, type);
        } catch (Exception e) {
            log.warn("[cache] 读取失败 key={}, {}", key, e.getMessage());
            return null;
        }
    }

    @Override
    public <T> T getOrLoad(String key, Class<T> type, Duration ttl, Supplier<T> loader) {
        T cached = get(key, type);
        if (cached != null) {
            return cached;
        }
        T value = loader.get();
        if (value != null) {
            set(key, value, ttl);
        }
        return value;
    }

    @Override
    public void set(String key, Object value, Duration ttl) {
        try {
            String json = objectMapper.writeValueAsString(value);
            if (ttl == null || ttl.isZero() || ttl.isNegative()) {
                redisTemplate.opsForValue().set(key, json);
            } else {
                redisTemplate.opsForValue().set(key, json, ttl);
            }
        } catch (Exception e) {
            log.warn("[cache] 写入失败 key={}, {}", key, e.getMessage());
        }
    }

    @Override
    public void delete(String key) {
        try {
            redisTemplate.delete(key);
        } catch (Exception e) {
            log.warn("[cache] 删除失败 key={}, {}", key, e.getMessage());
        }
    }

    @Override
    public void deleteByBiz(String biz) {
        try {
            Set<String> keys = redisTemplate.keys(prefix + ':' + biz + ":*");
            if (keys != null && !keys.isEmpty()) {
                redisTemplate.delete(keys);
            }
        } catch (Exception e) {
            log.warn("[cache] 批量删除失败 biz={}, {}", biz, e.getMessage());
        }
    }
}
